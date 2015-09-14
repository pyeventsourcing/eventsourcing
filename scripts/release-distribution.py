#!/usr/bin/env python
import os
import subprocess
import sys


def build_and_release(cwd):
    # Build and upload to Test PyPI.
    subprocess.check_call([sys.executable, 'setup.py', 'sdist', 'upload', '-r', 'pypi'], cwd=cwd)


if __name__ == '__main__':
    cwd = os.path.join(os.environ['HOME'], 'PyCharmProjects', 'eventsourcing')
    build_and_release(cwd)
