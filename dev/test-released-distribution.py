#!/usr/bin/env python
import os
import subprocess


def main():
    # Validate current working dir (should be project root).
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

    # Declare temporary working directory variable.
    build_targets = [
        (os.path.join(proj_path, "tmpve3.7"), "python")
    ]
    for (venv_path, python_bin) in build_targets:

        # Rebuild virtualenv.
        subprocess.check_call(["rm", "-r", venv_path], cwd=proj_path)
        subprocess.check_call(["virtualenv", "-p", python_bin, venv_path],
                              cwd=proj_path)
        subprocess.check_call(["bin/pip", "install", "-U", "pip", "wheel"],
                              cwd=venv_path)

        # Install from PyPI.
        os.environ["CASS_DRIVER_NO_CYTHON"] = "1"
        subprocess.check_call(
            ["bin/pip", "install", "--no-cache-dir", "eventsourcing[testing]"],
            cwd=venv_path,
        )

        # Check installed tests all pass.
        subprocess.check_call(
            ["bin/python", "-m" "unittest", "discover", "eventsourcing.tests"],
            cwd=venv_path
        )


if __name__ == "__main__":
    main()
