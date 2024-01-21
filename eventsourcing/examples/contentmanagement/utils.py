from __future__ import annotations

import os
from tempfile import TemporaryDirectory


def create_diff(old: str, new: str) -> str:
    return run("diff %s %s > %s", old, new)


def apply_patch(old: str, diff: str) -> str:
    return run("patch -s %s %s -o %s", old, diff)


def run(cmd: str, a: str, b: str) -> str:
    with TemporaryDirectory() as td:
        a_path = os.path.join(td, "a")
        b_path = os.path.join(td, "b")
        c_path = os.path.join(td, "c")
        with open(a_path, "w") as a_file:
            a_file.write(a)
        with open(b_path, "w") as b_file:
            b_file.write(b)
        os.system(cmd % (a_path, b_path, c_path))  # noqa: S605
        with open(c_path) as c_file:
            return c_file.read()
