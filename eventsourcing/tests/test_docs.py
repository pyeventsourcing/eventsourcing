import os
import sys
from glob import glob
from os.path import dirname, join
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
from unittest.case import TestCase, expectedFailure

import eventsourcing


base_dir = dirname(dirname(eventsourcing.__file__))


class TestDocs(TestCase):
    def test_code_snippets_in_readme(self):
        path = join(base_dir, 'README.md')
        self.check_code_snippets_in_file(path)

    def test_code_snippets_in_docs(self):
        for path in glob(join(base_dir, 'docs', '*', '*.rst')):
            print("Testing code snippets in {}".format(path))
            self.check_code_snippets_in_file(path)

    def check_code_snippets_in_file(self, doc_path):
        # Extract lines of Python code from the README.md file.

        if not os.path.exists(doc_path):
            self.skipTest("Skipped test because usage instructions in README file are "
                          "not available for testing once this package is installed")

        lines = []
        count_code_lines = 0
        is_code = False
        is_md = False
        is_rst = False
        with open(doc_path) as doc_file:
            for line in doc_file:
                line = line.strip('\n')
                if is_code and is_md and line.startswith('```'):
                    is_code = False
                    line = ''
                elif is_code and is_rst and line and not line.startswith('    '):
                    is_code = False
                    line = ''
                elif is_code:
                    if is_rst:
                        line = line[4:]
                    count_code_lines += 1
                elif line.startswith('```python'):
                    is_code = True
                    is_md = True
                    line = ''
                elif line.startswith('.. code:: python'):
                    is_code = True
                    is_rst = True
                    line = ''
                else:
                    line = ''
                lines.append(line)

        print("There are {} lines of code in {}".format(count_code_lines, doc_path))

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
        self.assertEqual(exit_status, 0, "Usage exit status {}:\n{}\n{}".format(exit_status, out, err))

        # Close (deletes) the tempfile.
        tempfile.close()
