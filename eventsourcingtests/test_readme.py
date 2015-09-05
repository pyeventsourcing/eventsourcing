import os
import unittest
from subprocess import Popen, PIPE
import sys


class TestUsage(unittest.TestCase):

    def test(self):
        # Extract lines of Python code from the README.md file.
        code_lines = []
        is_code = False
        readme_filename = 'README.md'
        readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), readme_filename)
        temp_filename = '.README.py'
        temp_path = os.path.join(os.path.dirname(readme_path), temp_filename)
        count_code_lines = 0
        for line in open(readme_path):
            if is_code and line.startswith('```'):
                is_code = False
                code_lines.append('')
            elif is_code:
                code_lines.append(line.strip('\n'))
                count_code_lines += 1
            elif line.startswith('```python'):
                is_code = True
                code_lines.append('')
            else:
                code_lines.append('')

        code = "\n".join(code_lines) + '\n'

        self.assertTrue(count_code_lines)

        # Write the code into a temp file.
        with open(temp_path, 'w+') as readme_py:
            readme_py.writelines(code)

        # Run the code and catch errors.
        p = Popen([sys.executable, temp_path], stdout=PIPE, stderr=PIPE)
        out, err = p.communicate()
        out = out.decode('utf8').replace(temp_filename, readme_filename)
        err = err.decode('utf8').replace(temp_filename, readme_filename)
        exit_status = p.wait()

        # Check for errors running the code.
        self.assertEqual(exit_status, 0, "Usage exit status {}:\n{}\n{}".format(exit_status, out, err))

        # Delete the temp file.
        os.unlink(temp_path)
