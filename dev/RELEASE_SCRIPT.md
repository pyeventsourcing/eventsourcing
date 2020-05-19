# How to make a new release

Steps to make a new release.

1. Decide new version number.
1. Start release, named after new release version.
1. Increase version number to new release version plus 'rc0'.
1. Commit, and push branch to GitHub and start a PR to master.
1. Review versions of all dependencies.
1. Update release notes to describe what's new in this release.
1. Update copyright year in LICENSE file.
1. Run 'make prepare-distribution'.
1. Increase version number to 'rc1', 'rc2' in case of failure.
1. Try to fix and push changes to GitHub.
1. Make changes until built distribution is working.
1. When all tests passing, increase version number to release version (edit and commit).
1. Finish release (merge into master and develop). Tag master 'vX.Y.Z'.
1. Push all changes to GitHub.
1. Checkout master branch (at the tag).
1. Run 'make release-distribution'.
1. Run './dev/test-released-distribution' script (from project root directory).
1. Manually check documentation has been built and installed.
1. Manually check PyPI.
1. Manually check GitHub.
1. Checkout develop branch.
1. Increase version number to the next 'dev0'.
