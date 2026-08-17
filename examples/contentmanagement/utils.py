from __future__ import annotations

from diff_match_patch import diff_match_patch

dmp = diff_match_patch()


def create_diff(old: str, new: str) -> str:
    # Generate the diff
    diffs = dmp.diff_main(old, new)
    # Clean up the diff to make it more human-readable/semantic
    dmp.diff_cleanupSemantic(diffs)
    # Convert it to a patch string
    patches = dmp.patch_make(old, diffs)
    return dmp.patch_toText(patches)


def apply_diff(old: str, diff_text: str) -> str:
    # Parse the patch string
    patches = dmp.patch_fromText(diff_text)
    # Apply it to the old text
    new_text, results = dmp.patch_apply(patches, old)

    # results is a list of booleans indicating if each chunk applied cleanly
    if not all(results):
        msg = "Patch failed to apply perfectly"
        raise ValueError(msg)

    return new_text
