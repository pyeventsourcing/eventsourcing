import os
import subprocess
import sys


def main():
    # Validate current working dir (should be project root).
    proj_path = os.path.abspath(".")
    readme_path = os.path.join(proj_path, "README.md")
    if os.path.exists(readme_path):
        assert "A library for event sourcing in Python" in open(readme_path).read()
    else:
        raise Exception("Couldn't find project README.md")

    # Build and upload to PyPI.
    subprocess.check_call([sys.executable, "setup.py", "clean", "--all"], cwd=proj_path)
    subprocess.check_call(
        [sys.executable, "setup.py", "sdist", "upload", "-r", "pypi"], cwd=proj_path
    )


if __name__ == "__main__":
    main()
