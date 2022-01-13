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
    subprocess.check_call([sys.executable, "setup.py", "sdist", "bdist_wheel"], cwd=proj_path)

    version_path = os.path.join(proj_path, "eventsourcing", "__init__.py")
    version = open(version_path).readlines()[0].split("=")[-1].strip().strip('"')
    sdist_path = os.path.join(
        proj_path, 'dist', f'eventsourcing-{version}.tar.gz'
    )
    bdist_path = os.path.join(
        proj_path, 'dist', f'eventsourcing-{version}-py3-none-any.whl'
    )

    subprocess.check_call([sys.executable, "-m", "pip", "install", "-U", "twine"], cwd=proj_path)
    subprocess.check_call(
        [sys.executable, "-m", "twine", "upload", sdist_path, bdist_path], cwd=proj_path
    )

#     twine upload ./dist/eventsourcing-VERSION.tar.gz


if __name__ == "__main__":
    main()
