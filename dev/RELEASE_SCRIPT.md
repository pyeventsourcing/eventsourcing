# How to make a new release

Steps to make a new release.

1. Review versions of all dependencies.
2. Go to the minor version branch, or create a minor version branch.
3. Check release notes describe what's new in this release.
4. Increase version number to new release version number.
5. Check copyright year in LICENSE file.
6. Run 'make prepush'.
7. Run 'make prepare-distribution'.
8. Fix any errors, until built distribution is working.
9. Push changes to GitHub and wait for CI to pass.
10. Set date of release in release notes, commit.
10. Adjust links in README file.
11. Create a Git tag with the number of the version, prefixed with 'v' and set the message to the same thing.
12. Push tag to GitHub, and wait for docs to build.
13. Fix the links at the top of the README file (branch should point to branch, main to most recent release branch).
14. Run 'twine upload ./dist/eventsourcing-VERSION.tar.gz'.
15. Run './dev/test-released-distribution' script (from project root directory).
16. Check documentation has been built and installed.
17. Check PyPI shows new release.
18. Checkout main branch.
19. Merge changes into main branch.
20. Check version number on main branch is next minor version + '.0dev0'.
