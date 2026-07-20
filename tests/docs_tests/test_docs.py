import os
import signal
import sys
import traceback
from pathlib import Path
from subprocess import PIPE, Popen
from tempfile import NamedTemporaryFile
from types import ModuleType
from unittest.case import TestCase

import eventsourcing
from eventsourcing.domain import datetime_now_with_tzinfo
from eventsourcing.tests.persistence import tmpfile_uris
from eventsourcing.tests.postgres_utils import drop_tables
from eventsourcing.utils import clear_topic_cache

base_dir = Path(eventsourcing.__file__).resolve().parent.parent


class TestDocs(TestCase):
    def setUp(self) -> None:
        drop_tables()
        super().setUp()
        self.uris = tmpfile_uris()
        self.os_environ_copy = os.environ.copy()
        self.orig_main = sys.modules["__main__"]
        self.original_sigint_handler = signal.getsignal(signal.SIGINT)

        # Then, later...

    def tearDown(self) -> None:
        self.restore_environ()

    def restore_environ(self) -> None:
        signal.signal(signal.SIGINT, self.original_sigint_handler)
        sys.modules["__main__"] = self.orig_main
        for key in list(os.environ.keys()):
            if key not in self.os_environ_copy:
                del os.environ[key]
            else:
                os.environ[key] = self.os_environ_copy[key]
        clear_topic_cache()
        drop_tables()

    def clean_env(self) -> None:
        drop_tables()

    def test_readme(self) -> None:
        self._out = ""

        path = base_dir / "README.md"
        if not Path.exists(path):
            self.skipTest(f"Skipped test, README file not found: {path}")

        started = datetime_now_with_tzinfo()
        try:
            self.check_code_snippets_in_file(path, failures=[])
        except:
            duration = datetime_now_with_tzinfo() - started
            print(f"FAIL after {duration}s")
            raise
        else:
            duration = datetime_now_with_tzinfo() - started
            print(f"PASS after {duration}s")
        # finally:
        #
        #     Path("dog-school.db").unlink()

        # path = join(base_dir, "README_example_with_axon.md")
        # if not os.path.exists(path):
        #     self.skipTest("Skipped test, README file not found: {}".format(path))
        # self.check_code_snippets_in_file(path)

    def test_docs(self) -> None:
        skipped = [
            "aggregate6.rst",  # has :start-from: complications...
            "part4.rst",  # can't import abstract test case that is del-ed in module
        ]

        self._out = ""
        docs_path = base_dir / "docs"

        if not Path.exists(docs_path):
            self.skipTest(f"Skipped test, docs folder not found: {docs_path}")

        file_paths = []
        for dirpath, _, filenames in os.walk(docs_path):
            for name in filenames:
                file_path = docs_path / dirpath / name

                if name in skipped:
                    continue
                if name.endswith(".rst"):
                    # if (
                    #     name.endswith("persistence.rst")
                    #     or name.endswith("domain.rst")
                    #       or name.endswith("application.rst")
                    #     or name.endswith("system.rst")
                    #     or name.endswith("examples.rst")
                    # ):
                    # if name.endswith('part4.rst'):
                    # if name.endswith('aggregates_in_ddd.rst'):
                    # if name.endswith('example_application.rst'):
                    # if name.endswith('everything.rst'):
                    # if name.endswith('infrastructure.rst'):
                    # if name.endswith('application.rst'):
                    # if name.endswith('snapshotting.rst'):
                    # if name.endswith('notifications.rst'):
                    # if name.endswith('projections.rst'):
                    # if name.endswith('deployment.rst'):
                    # if name.endswith('process.rst'):
                    file_paths.append(file_path)

        file_paths = sorted(file_paths)
        failures: list[tuple[Path, str]] = []
        passed = []
        print("Testing code snippets in docs:")
        for path in file_paths:
            print(path)
        print()
        total_duration = 0.0
        for path in file_paths:
            # print("Testing code snippets in file: {}".format(path))
            started = datetime_now_with_tzinfo()
            try:
                try:
                    os.environ["EVENTSOURCING_DISABLE_REDEFINITION_CHECK"] = "y"
                    self.check_code_snippets_in_file(path, failures=failures)
                finally:
                    del os.environ["EVENTSOURCING_DISABLE_REDEFINITION_CHECK"]

            except self.failureException:
                duration = (datetime_now_with_tzinfo() - started).total_seconds()
                total_duration += duration
                print(f"FAIL after {duration}s")
                print()
            else:
                passed.append(path)
                duration = (datetime_now_with_tzinfo() - started).total_seconds()
                total_duration += duration
                print(f"PASS after {duration}s")
                print()
            finally:
                self.restore_environ()

        print(f"{len(failures)} failed, {len(passed)} passed")
        print(f"total duration: {total_duration}s")

        if failures:
            report = "\n"
            for doc_path, error in failures:
                report += f"FAILED DOC: {doc_path}\nERROR: {error}\n"
            self.fail(
                f"\n{report}\nFAILED DOCS: {len(failures)} "
                f"docs failed (see above for details)"
            )

    def check_code_snippets_in_file(
        self, doc_path: Path, failures: list[tuple[Path, str]]
    ) -> None:
        # Extract lines of Python code from the README.md file.

        lines = []
        num_code_lines = 0
        num_code_lines_in_block = 0
        is_code = False
        is_md = False
        is_rst = False
        last_line = ""
        is_literalinclude = False
        module = ""
        with doc_path.open() as doc_file:
            for line_index, orig_line in enumerate(doc_file):
                # print("Line index:", line_index)
                # print("Orig line:", orig_line)
                # print("Last line:", last_line)

                line = orig_line.strip("\n")
                if line.startswith("```python"):
                    # Start markdown code block.
                    if is_rst:
                        self.fail(
                            "Markdown code block found after restructured text block "
                            "in same file."
                        )
                    is_code = True
                    is_md = True
                    line = ""
                    num_code_lines_in_block = 0
                elif is_code and is_md and line.startswith("```"):
                    # Finish markdown code block.
                    if not num_code_lines_in_block:
                        self.fail(f"No lines of code in block: {line_index + 1}")
                    is_code = False
                    line = ""
                elif is_code and is_rst and line.startswith("```"):
                    # Can't finish restructured text block with markdown.
                    self.fail(
                        "Restructured text block terminated with markdown format '```'"
                    )
                elif line.startswith(".. code-block:: python") or (
                    line.strip() == ".." and "include-when-testing" in last_line
                ):
                    # Start restructured text code block.
                    if is_md:
                        self.fail(
                            "Restructured text code block found after markdown block "
                            "in same file."
                        )
                    is_code = True
                    is_rst = True
                    line = ""
                    num_code_lines_in_block = 0
                elif line.startswith(".. literalinclude::"):
                    is_literalinclude = True
                    literal_include_path = line.strip().split(" ")[
                        -1
                    ]  # get the file path
                    module = literal_include_path[:-3]  # remove the '.py' from the end
                    module = module.lstrip("./")  # remove all the ../../..
                    module = module.replace("/", ".")  # swap dots for slashes
                    line = ""

                elif is_literalinclude:
                    if "pyobject" in line:
                        # Assume ".. literalinclude:: ../../xxx/xx.py"
                        # Or ".. literalinclude:: ../xxx/xx.py"
                        # Assume "    :pyobject: xxxxxx"
                        pyobject = line.strip().split(" ")[-1]
                        statement = f"from {module} import {pyobject}"
                        line = statement
                    elif not line.strip():
                        is_literalinclude = False
                        module = ""

                elif is_code and is_rst and line and not line.startswith(" "):
                    # Finish restructured text code block.
                    if not num_code_lines_in_block:
                        self.fail(f"No lines of code in block: {line_index + 1}")
                    is_code = False
                    line = ""
                elif ":emphasize-lines:" in line:
                    line = ""
                elif is_code:
                    # Process line in code block. Restructured code block normally
                    # indented with four spaces.
                    if is_rst and len(line.strip()):
                        if not line.startswith("    "):
                            self.fail(
                                f"Code line needs 4-char indent: {line!r}: {doc_path}"
                            )
                        # Strip four chars of indentation.
                        line = line[4:]

                    if len(line.strip()):
                        num_code_lines_in_block += 1
                        num_code_lines += 1
                else:
                    line = ""
                lines.append(line)
                # if orig_line.strip():
                last_line = orig_line

        print(f"{num_code_lines} lines of code in {doc_path}")

        if num_code_lines == 0:
            return

        # Execute the code.
        lines[0] = "from __future__ import annotations"
        lines[1] = "from eventsourcing.domain import datetime_now_with_tzinfo"
        lines[2] = "started = datetime_now_with_tzinfo()"
        lines.append(
            "print(f'exec duration: "
            "{(datetime_now_with_tzinfo() - started).total_seconds()}s')"
        )

        source = "\n".join(lines) + "\n"

        try:
            code = compile(source, "__main__", "exec")
            exec_module = ModuleType("__main__")
            sys.modules["__main__"] = exec_module
            exec(code, exec_module.__dict__)  # noqa: S102
        except BaseException:
            error = traceback.format_exc()
            error = error.replace('File "__main__",', f'File "{doc_path}"')
            print(f"FAILED DOC: {doc_path}\nERROR: {error}\n")
            failures.append((doc_path, error))
            raise self.failureException from None

        print("Code executed OK")

        # Check the code with mypy and catch errors.
        with NamedTemporaryFile("w+") as tempfile:
            temp_path = tempfile.name
            tempfile.writelines(source)
            tempfile.flush()

            p = Popen(  # noqa: S603
                [
                    sys.executable,
                    "-m",
                    "mypy",
                    # "--disable-error-code=no-redef",
                    # "--disable-error-code=attr-defined",
                    # "--disable-error-code=name-defined",
                    # "--disable-error-code=truthy-function",
                    temp_path,
                ],
                stdout=PIPE,
                stderr=PIPE,
                env={
                    "PYTHONPATH": base_dir,
                },
                encoding="utf-8",
            )

            out, err = p.communicate()

            # # Run the code and catch errors.
            # p = Popen(  # no qa: S603
            #     [sys.executable, temp_path],
            #     stdout=PIPE,
            #     stderr=PIPE,
            #     env={"PYTHONPATH": base_dir},
            #     encoding="utf-8",
            # )
            # out, err = p.communicate()
        # out = out.decode("utf8")
        # err = err.decode("utf8")

        # To get clickable links in PyCharm console, prefix absolute paths
        # with "file://". Using paths relative to project root folder doesn't work.
        # Actually doesn't work because PyCharm tries to open the file in a browser.
        # out = out.replace(temp_path, "file://" + str(doc_path)[:-4]+".py")
        # err = err.replace(temp_path, "file://" + str(doc_path)[:-4]+".py")

        # Got clickable links with PyCharm plugin "Clickable Output Links"
        # https://github.com/Shadow-Devil/output-link-filter

        out = out.replace(temp_path, str(doc_path))
        out = out.replace(": error:", " error:")

        exit_status = p.wait()

        # Check for errors running the code.
        if exit_status:
            print("Mypy errors:")
            print(out)
            print(err)
            # self.fail(out + err)
        else:
            print("No mypy errors")
