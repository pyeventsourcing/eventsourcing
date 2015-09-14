#!/usr/bin/env python
import os
import subprocess


del os.environ['PYTHONPATH']


def get_version():
    return [line.split('=')[1].strip().strip(",").strip("'") for line in open('../setup.py').readlines() if 'version' in line][0]


def test_released_distribution(cwd):
    # Declare temporary working directory variable.
    tmpcwd27 = os.path.join(cwd, 'tmpve2.7')
    tmpcwd34 = os.path.join(cwd, 'tmpve3.4')

    for (tmpcwd, python_executable) in [(tmpcwd27, 'python2.7'), (tmpcwd34, 'python3.4')]:

        # Rebuild virtualenvs.
        rebuild_virtualenv(cwd, tmpcwd, python_executable)

        # Install from PyPI.
        subprocess.check_call(['bin/pip', 'install', '--no-cache-dir', '-U', 'eventsourcing[test]'], cwd=tmpcwd)

        # Check installed tests all pass.
        test_installation(tmpcwd)


def test_installation(tmpcwd):
    subprocess.check_call(['bin/python', '-m', 'dateutil.parser'], cwd=tmpcwd)
    subprocess.check_call(['bin/python', '-m' 'unittest', 'discover', 'eventsourcingtests'], cwd=tmpcwd)


def rebuild_virtualenv(cwd, venv_path, python_executable):
    subprocess.check_call(['rm', '-rf', venv_path], cwd=cwd)
    subprocess.check_call(['virtualenv', '-p', python_executable, venv_path], cwd=cwd)


if __name__ == '__main__':
    cwd = os.path.join(os.environ['HOME'], 'PyCharmProjects', 'eventsourcing')
    test_released_distribution(cwd)

