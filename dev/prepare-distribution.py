#!/usr/bin/env python
import os
import subprocess
import sys
from subprocess import CalledProcessError
from time import sleep

try:
    del os.environ["PYTHONPATH"]
except KeyError:
    pass

os.environ["CASS_DRIVER_NO_CYTHON"] = "1"
sys.path.insert(0, "../")
from eventsourcing import __version__


def build_and_test(cwd):
    # Declare temporary working directory variable.
    # tmpcwd27 = os.path.join(cwd, 'tmpve2.7')
    tmpcwd37 = os.path.join(cwd, "tmpve3.7")

    # Build distribution.
    subprocess.check_call([sys.executable, "setup.py", "clean", "--all"], cwd=cwd)
    subprocess.check_call([sys.executable, "setup.py", "sdist"], cwd=cwd)
    is_uploaded_testpypi = False

    targets = [
        # (tmpcwd27, 'python2.7'),
        (tmpcwd37, "python")
    ]
    for (tmpcwd, python_executable) in targets:

        check_locally = False
        if check_locally:
            # Rebuild virtualenvs.
            rebuild_virtualenv(cwd, tmpcwd, python_executable)

            # Install from dist folder.
            tar_path = "../dist/eventsourcing-{}.tar.gz[testing]".format(__version__)
            subprocess.check_call(["bin/pip", "install", "-U", tar_path], cwd=tmpcwd)

            # Check installed tests all pass.
            test_installation(tmpcwd)

        # Build and upload to Test PyPI.
        if not is_uploaded_testpypi:
            subprocess.check_call(
                [sys.executable, "setup.py", "sdist", "upload", "-r", "pypitest"],
                cwd=cwd,
            )
            is_uploaded_testpypi = True

        # Rebuild virtualenvs.
        rebuild_virtualenv(cwd, tmpcwd, python_executable)

        # Install from Test PyPI.
        cmd = [
            "bin/pip",
            "install",
            "-U",
            "eventsourcing[testing]==" + __version__,
            "--index-url",
            "https://testpypi.python.org/simple",
            "--extra-index-url",
            "https://pypi.python.org/simple",
        ]

        patience = 10
        while patience:
            try:
                subprocess.check_call(cmd, cwd=tmpcwd)
                break
            except CalledProcessError:
                patience -= 1
                print("Patience:", patience)
                sleep(6)

        # Check installed tests all pass.
        test_installation(tmpcwd)

        remove_virtualenv(cwd, tmpcwd)


def test_installation(tmpcwd):
    subprocess.check_call(
        ["bin/python", "-m" "unittest", "discover", "eventsourcing.tests"], cwd=tmpcwd
    )


def rebuild_virtualenv(cwd, venv_path, python_executable):
    remove_virtualenv(cwd, venv_path)
    subprocess.check_call(["virtualenv", "-p", python_executable, venv_path], cwd=cwd)
    subprocess.check_call(["bin/pip", "install", "-U", "pip", "wheel"], cwd=venv_path)


def remove_virtualenv(cwd, venv_path):
    subprocess.check_call(["rm", "-rf", venv_path], cwd=cwd)


if __name__ == "__main__":
    cwd = os.path.join(os.environ["HOME"], "PyCharmProjects", "eventsourcing")
    build_and_test(cwd)
