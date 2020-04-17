#!/usr/bin/env python
import os
import subprocess

if "PYTHONPATH" in os.environ:
    del os.environ["PYTHONPATH"]


def test_released_distribution(cwd):
    # Declare temporary working directory variable.
    tmpcwd27 = os.path.join(cwd, "tmpve2.7")
    tmpcwd36 = os.path.join(cwd, "tmpve3.6")
    tmpcwd37 = os.path.join(cwd, "tmpve3.7")

    build_targets = [
        # (tmpcwd27, 'python2.7'),
        # (tmpcwd36, 'python3.6'),
        (tmpcwd37, "python")
    ]
    for (tmpcwd, python_executable) in build_targets:

        # Rebuild virtualenvs.
        rebuild_virtualenv(cwd, tmpcwd, python_executable)

        # Install from PyPI.
        os.environ["CASS_DRIVER_NO_CYTHON"] = "1"
        subprocess.check_call(
            ["bin/pip", "install", "--no-cache-dir", "eventsourcing[testing]"],
            cwd=tmpcwd,
        )

        # Check installed tests all pass.
        test_installation(tmpcwd)


def test_installation(tmpcwd):
    subprocess.check_call(
        ["bin/python", "-m" "unittest", "discover", "eventsourcing.tests"], cwd=tmpcwd
    )


def rebuild_virtualenv(cwd, venv_path, python_executable):
    subprocess.check_call(["rm", "-rf", venv_path], cwd=cwd)
    subprocess.check_call(["virtualenv", "-p", python_executable, venv_path], cwd=cwd)
    subprocess.check_call(["bin/pip", "install", "-U", "pip", "wheel"], cwd=venv_path)


if __name__ == "__main__":
    cwd = os.path.join(os.environ["HOME"], "PyCharmProjects", "eventsourcing")
    test_released_distribution(cwd)
