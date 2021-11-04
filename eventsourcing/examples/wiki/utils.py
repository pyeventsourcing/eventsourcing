import os
from tempfile import TemporaryDirectory


def diff(old: str, new: str) -> str:
    with TemporaryDirectory() as td:
        old_file_path = os.path.join(td, "old")
        new_file_path = os.path.join(td, "new")
        out_file_path = os.path.join(td, "out")
        with open(old_file_path, "w") as old_file:
            old_file.write(old)
        with open(new_file_path, "w") as new_file:
            new_file.write(new)
        os.system(f"diff {old_file.name} {new_file.name} > {out_file_path}")
        with open(out_file_path, "r") as out_file:
            diff = out_file.read()
            return diff


def patch(orig: str, patch: str) -> str:
    with TemporaryDirectory() as td:
        orig_file_path = os.path.join(td, "orig")
        patch_file_path = os.path.join(td, "patch")
        out_file_path = os.path.join(td, "out")
        with open(orig_file_path, "w") as orig_file:
            orig_file.write(orig)
        with open(patch_file_path, "w") as patch_file:
            patch_file.write(patch)
        os.system(f"patch -s {orig_file_path} {patch_file_path} -o {out_file_path}")
        with open(out_file_path, "r") as out_file:
            body = out_file.read()
            return body
