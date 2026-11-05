"""Repository hygiene checks run by pre-commit.

These replace the third-party `pre-commit-hooks` and `conventional-pre-commit`
repositories so that no hook code is fetched from outside this repo; the only
external code involved is what is pinned in `uv.lock`.

Usage (see .pre-commit-config.yaml):

    python -m hooks.checks <check> [args...]

Each check returns a list of problems and exits non-zero if there are any. The
two "fixer" checks rewrite files in place and also exit non-zero when they
changed something, so the commit stops and the change can be reviewed and staged.
"""

import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path

import yaml

MAX_FILE_KB = 500

CONVENTIONAL_TYPES = (
    "feat",
    "fix",
    "docs",
    "style",
    "refactor",
    "perf",
    "test",
    "build",
    "ci",
    "chore",
    "revert",
)
_CONVENTIONAL = re.compile(rf"^({'|'.join(CONVENTIONAL_TYPES)})(\([\w./-]+\))?!?: \S")
# Messages git or the developer generates on purpose and that need no prefix.
_CONVENTIONAL_EXEMPT = re.compile(r'^(Merge |Revert "|fixup! |squash! |amend! )')

_PRIVATE_KEY = re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY")
_TRAILING_WHITESPACE = re.compile(rb"[ \t]+(\r?)$", re.MULTILINE)


def _read(path: str) -> bytes:
    return Path(path).read_bytes()


def trailing_whitespace(paths: Sequence[str]) -> list[str]:
    """Strip trailing spaces and tabs from every line, in place."""
    changed = []
    for path in paths:
        data = _read(path)
        if b"\0" in data:
            continue
        fixed = _TRAILING_WHITESPACE.sub(rb"\1", data)
        if fixed != data:
            Path(path).write_bytes(fixed)
            changed.append(f"{path}: removed trailing whitespace")
    return changed


def end_of_file(paths: Sequence[str]) -> list[str]:
    """Make every non-empty file end with exactly one newline, in place."""
    changed = []
    for path in paths:
        data = _read(path)
        if not data or b"\0" in data:
            continue
        newline = b"\r\n" if data.endswith(b"\r\n") else b"\n"
        body = data.rstrip(b"\r\n")
        fixed = body + newline if body else b""
        if fixed != data:
            Path(path).write_bytes(fixed)
            changed.append(f"{path}: fixed end of file")
    return changed


def check_yaml(paths: Sequence[str]) -> list[str]:
    problems = []
    for path in paths:
        try:
            with open(path, encoding="utf-8") as handle:
                list(yaml.safe_load_all(handle))
        except (yaml.YAMLError, UnicodeDecodeError) as error:
            problems.append(f"{path}: invalid YAML: {error}")
    return problems


def check_toml(paths: Sequence[str]) -> list[str]:
    problems = []
    for path in paths:
        try:
            tomllib.loads(_read(path).decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as error:
            problems.append(f"{path}: invalid TOML: {error}")
    return problems


def check_merge_conflict(paths: Sequence[str]) -> list[str]:
    problems = []
    for path in paths:
        for number, line in enumerate(_read(path).splitlines(), start=1):
            if line.startswith((b"<<<<<<< ", b">>>>>>> ")):
                problems.append(f"{path}:{number}: merge conflict marker")
    return problems


def check_large_files(paths: Sequence[str]) -> list[str]:
    problems = []
    for path in paths:
        size_kb = Path(path).stat().st_size / 1024
        if size_kb > MAX_FILE_KB:
            problems.append(f"{path}: {size_kb:.0f} KB exceeds the {MAX_FILE_KB} KB limit")
    return problems


def check_private_keys(paths: Sequence[str]) -> list[str]:
    return [f"{path}: contains a private key" for path in paths if _PRIVATE_KEY.search(_read(path))]


def check_branch(branches: Sequence[str]) -> list[str]:
    """Refuse to commit directly on a protected branch (default: main)."""
    protected = set(branches) or {"main"}
    result = subprocess.run(  # noqa: S603
        ["git", "symbolic-ref", "--short", "HEAD"],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
    )
    current = result.stdout.strip()
    if current in protected:
        return [f"direct commits to '{current}' are not allowed; create a branch first"]
    return []


def check_commit_message(paths: Sequence[str]) -> list[str]:
    """Require a Conventional Commits subject line (`type(scope): description`)."""
    lines = [
        line
        for line in Path(paths[0]).read_text(encoding="utf-8").splitlines()
        if not line.startswith("#")
    ]
    subject = next((line for line in lines if line.strip()), "")
    if _CONVENTIONAL_EXEMPT.match(subject) or _CONVENTIONAL.match(subject):
        return []
    return [
        f"commit message does not follow Conventional Commits: {subject!r}\n"
        f"  expected '<type>: <description>' where type is one of: {', '.join(CONVENTIONAL_TYPES)}"
    ]


CHECKS: dict[str, Callable[[Sequence[str]], list[str]]] = {
    "trailing-whitespace": trailing_whitespace,
    "end-of-file": end_of_file,
    "check-yaml": check_yaml,
    "check-toml": check_toml,
    "check-merge-conflict": check_merge_conflict,
    "check-large-files": check_large_files,
    "check-private-keys": check_private_keys,
    "check-branch": check_branch,
    "check-commit-message": check_commit_message,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in CHECKS:
        print(f"usage: python -m hooks.checks {{{'|'.join(CHECKS)}}} [args...]", file=sys.stderr)
        return 2
    problems = CHECKS[args[0]](args[1:])
    for problem in problems:
        print(problem)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
