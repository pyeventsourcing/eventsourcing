#!/usr/bin/env python
import os
import subprocess
import sys
from subprocess import CalledProcessError
from time import sleep


def main():
    proj_path = os.path.abspath(".")
    readme_path = os.path.join(proj_path, "README.md")
    if os.path.exists(readme_path):
        assert "A library for event sourcing in Python" in open(readme_path).read()
    else:
        raise Exception("Couldn't find project README.md")

    try:
        del os.environ["PYTHONPATH"]
    except KeyError:
        pass

    # Build and upload to Test PyPI.
    subprocess.check_call([sys.executable, "setup.py", "clean", "--all"], cwd=proj_path)
    try:
        subprocess.check_call(
            [sys.executable, "setup.py", "sdist", "upload", "-r", "pypitest"],
            cwd=proj_path,
        )
    except CalledProcessError:
        sys.exit(1)

    # Test distribution for various targets.
    targets = [(os.path.join(proj_path, "tmpve3.7"), "python")]
    os.environ["CASS_DRIVER_NO_CYTHON"] = "1"
    from eventsourcing import __version__
    for (venv_path, python_bin) in targets:

        # Rebuild virtualenv.
        if os.path.exists(venv_path):
            remove_virtualenv(proj_path, venv_path)
        subprocess.check_call(
            ["virtualenv", "-p", python_bin, venv_path], cwd=proj_path
        )
        subprocess.check_call(
            ["bin/pip", "install", "-U", "pip", "wheel"], cwd=venv_path
        )

        # Install from Test PyPI.
        pip_install_from_testpypi = [
            os.path.join(venv_path, "bin/pip"),
            "install",
            "-U",
            "eventsourcing[testing]==" + __version__,
            "--index-url",
            "https://testpypi.python.org/simple",
            "--extra-index-url",
            "https://pypi.python.org/simple",
        ]

        patience = 10
        is_test_pass = False
        sleep(1)
        while True:
            try:
                subprocess.check_call(pip_install_from_testpypi, cwd=venv_path)
                is_test_pass = True
                break
            except CalledProcessError:
                patience -= 1
                if patience < 0:
                    break
                print("Patience:", patience)
                sleep(1)
        if not is_test_pass:
            print("Failed to install from testpypi.")
            sys.exit(1)

        # Check installed tests all pass.
        subprocess.check_call(
            ["bin/python", "-m" "unittest", "discover", "eventsourcing.tests"],
            cwd=venv_path,
        )

        remove_virtualenv(proj_path, venv_path)


def remove_virtualenv(proj_path, venv_path):
    subprocess.check_call(["rm", "-r", venv_path], cwd=proj_path)


if __name__ == "__main__":
    main()
