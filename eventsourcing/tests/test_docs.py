import os
import sys
from os.path import dirname, join
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
from unittest.case import TestCase

import eventsourcing
from eventsourcing.domain.model.events import assert_event_handlers_empty, clear_event_handlers
from eventsourcing.infrastructure.sqlalchemy.datastore import SQLAlchemyDatastore, SQLAlchemySettings
from eventsourcing.infrastructure.sqlalchemy.records import Base

base_dir = dirname(dirname(os.path.abspath(eventsourcing.__file__)))


class TestDocs(TestCase):
    def tearDown(self):
        clear_event_handlers()

        # Need to drop the stored events, because the __main__#Order topics
        # mess up the multiprocessing tests (because the Orders application
        # has the same ID so events from one test cause another to fail).
        os.environ['DB_URI'] = 'mysql+pymysql://{}:{}@{}/eventsourcing?charset=utf8mb4&binary_prefix=true'.format(
            os.getenv('MYSQL_USER', 'root'),
            os.getenv('MYSQL_PASSWORD', ''),
            os.getenv('MYSQL_HOST', '127.0.0.1'),
        )
        database = SQLAlchemyDatastore(settings=SQLAlchemySettings())
        database.setup_connection()
        # Might as well drop everything....
        Base.metadata.drop_all(database._engine)

        del (os.environ['DB_URI'])

    def test_readme(self):
        self._out = ''
        path = join(base_dir, 'README.md')
        if not os.path.exists(path):
            self.skipTest("Skipped test, README file not found: {}".format(path))
        self.check_code_snippets_in_file(path)

    def test_docs(self):

        skipped = [
            # 'deployment.rst'
        ]

        self._out = ''
        docs_path = os.path.join(base_dir, 'docs')

        if not os.path.exists(docs_path):
            self.skipTest("Skipped test, docs folder not found: {}".format(docs_path))

        file_paths = []
        for dirpath, _, filenames in os.walk(docs_path):
            for name in filenames:
                if name in skipped:
                    continue
                if name.endswith('.rst'):
                # if name.endswith('domainmodel.rst'):
                # if name.endswith('quick_start.rst'):
                # if name.endswith('aggregates_in_ddd.rst'):
                # if name.endswith('example_application.rst'):
                # if name.endswith('everything.rst'):
                # if name.endswith('infrastructure.rst'):
                # if name.endswith('application.rst'):
                # if name.endswith('snapshotting.rst'):
                # if name.endswith('notifications.rst'):
                # if name.endswith('projections.rst'):
                # if name.endswith('deployment.rst'):
                # if name.endswith('process.rst'):
                    file_paths.append(os.path.join(docs_path, dirpath, name))

        file_paths = sorted(file_paths)
        failures = []
        passed = []
        failed = []
        print("Testing code snippets in docs:")
        for path in file_paths:
            print(path)
        print('')
        for path in file_paths:
            # print("Testing code snippets in file: {}".format(path))
            try:
                self.check_code_snippets_in_file(path)
                assert_event_handlers_empty()
            except self.failureException as e:
                failures.append(e)
                failed.append(path)
                print(str(e).strip('\n'))
                print('FAIL')
                print('')
            else:
                passed.append(path)
                print('PASS')
                print('')
            finally:
                os.environ['SALT_FOR_DATA_INTEGRITY'] = ''

        print("{} failed, {} passed".format(len(failed), len(passed)))

        if failures:
            raise failures[0]

    def check_code_snippets_in_file(self, doc_path):
        # Extract lines of Python code from the README.md file.

        lines = []
        num_code_lines = 0
        num_code_lines_in_block = 0
        is_code = False
        is_md = False
        is_rst = False
        last_line = ''
        with open(doc_path) as doc_file:
            for orig_line in doc_file:
                line = orig_line.strip('\n')
                if line.startswith('```python'):
                    # Start markdown code block.
                    if is_rst:
                        self.fail("Markdown code block found after restructured text block in same file.")
                    is_code = True
                    is_md = True
                    line = ''
                    num_code_lines_in_block = 0
                elif is_code and is_md and line.startswith('```'):
                    # Finish markdown code block.
                    if not num_code_lines_in_block:
                        self.fail("No lines of code in block")
                    is_code = False
                    line = ''
                elif is_code and is_rst and line.startswith('```'):
                    # Can't finish restructured text block with markdown.
                    self.fail("Restructured text block terminated with markdown format '```'")
                elif line.startswith('.. code:: python') and 'exclude-when-testing' not in last_line:
                    # Start restructured text code block.
                    if is_md:
                        self.fail("Restructured text code block found after markdown block in same file.")
                    is_code = True
                    is_rst = True
                    line = ''
                    num_code_lines_in_block = 0
                elif is_code and is_rst and line and not line.startswith(' '):
                    # Finish restructured text code block.
                    if not num_code_lines_in_block:
                        self.fail("No lines of code in block")
                    is_code = False
                    line = ''
                elif is_code:
                    # Process line in code block.
                    if is_rst:
                        # Restructured code block normally indented with four spaces.
                        if len(line.strip()):
                            if not line.startswith('    '):
                                self.fail("Code line needs 4-char indent: {}: {}".format(repr(line), doc_path))
                            # Strip four chars of indentation.
                            line = line[4:]

                    if len(line.strip()):
                        num_code_lines_in_block += 1
                        num_code_lines += 1
                else:
                    line = ''
                lines.append(line)
                last_line = orig_line

        print("{} lines of code in {}".format(num_code_lines, doc_path))

        # Write the code into a temp file.
        tempfile = NamedTemporaryFile('w+')
        temp_path = tempfile.name
        tempfile.writelines("\n".join(lines) + '\n')
        tempfile.flush()

        # Run the code and catch errors.
        p = Popen([sys.executable, temp_path], stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        out = out.decode('utf8')
        err = err.decode('utf8')
        out = out.replace(temp_path, doc_path)
        err = err.replace(temp_path, doc_path)
        exit_status = p.wait()

        print(out)
        print(err)

        # Check for errors running the code.
        if exit_status:
            self.fail(out + err)

        # Close (deletes) the tempfile.
        tempfile.close()
