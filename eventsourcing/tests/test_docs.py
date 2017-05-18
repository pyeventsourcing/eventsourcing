import os
import sys
from os.path import dirname, join
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
from unittest.case import TestCase

import eventsourcing

base_dir = dirname(dirname(os.path.abspath(eventsourcing.__file__)))


class TestDocs(TestCase):
    def test_code_snippets_in_readme(self):
        self._out = ''
        path = join(base_dir, 'README.md')
        if not os.path.exists(path):
            self.skipTest("Skipped test, README file not found: {}".format(path))
        self.check_code_snippets_in_file(path)

    def test_code_snippets_in_docs(self):
        skipped = [
            'deployment.rst'
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
                    file_paths.append(os.path.join(docs_path, dirpath, name))

        file_paths = sorted(file_paths)
        failures = []
        passed = []
        failed = []
        print("Testing code snippets in docs:")
        for path in file_paths:
            print(path)
        print()
        for path in file_paths:
            # print("Testing code snippets in file: {}".format(path))
            try:
                self.check_code_snippets_in_file(path)
            except self.failureException as e:
                failures.append(e)
                failed.append(path)
                print(str(e).strip('\n'))
                print('FAIL')
                print()
            else:
                passed.append(path)
                print('PASS')
                print()
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
        with open(doc_path) as doc_file:
            for line in doc_file:
                line = line.strip('\n')
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
                elif line.startswith('.. code:: python'):
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
                                self.fail("Code line needs 4-char indent: {}".format(repr(line)))
                            # Strip four chars of indentation.
                            line = line[4:]

                    if len(line.strip()):
                        num_code_lines_in_block += 1
                        num_code_lines += 1
                else:
                    line = ''
                lines.append(line)

        print("{} lines of code in {}".format(num_code_lines, doc_path))

        # print(lines)
        # print('\n'.join(lines) + '\n')
        # Write the code into a temp file.
        tempfile = NamedTemporaryFile('w+')
        temp_path = tempfile.name

        # for line in lines:
        #     tempfile.write(line + '\n')
        tempfile.writelines("\n".join(lines) + '\n')
        tempfile.flush()

        # Run the code and catch errors.
        p = Popen([sys.executable, temp_path], stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        out = out.decode('utf8').replace(temp_path, doc_path)
        err = err.decode('utf8').replace(temp_path, doc_path)
        exit_status = p.wait()

        # Check for errors running the code.
        if exit_status:
            self.fail(out + err)

        # Close (deletes) the tempfile.
        tempfile.close()
