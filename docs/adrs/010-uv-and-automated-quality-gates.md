# ADR-010: uv for Dependencies and Automated Quality Gates

## Status

Accepted

## Date

2026-11-05

## Context

The project is open source and takes contributions from people with varying experience, and it will eventually hold sensitive case data. Two things were missing:

1. **Automated quality checks.** There was no linter, formatter, hook or CI. Style, unused code and common security mistakes were caught (or not) by review alone, and nothing stopped a broken commit reaching `main`.
2. **Reproducible dependencies.** `requirements.txt` pinned the direct dependencies only. Transitive dependencies floated, so a fresh install could differ from CI or production. Dev tools did not exist in any file, and the Python version was not declared anywhere.

Options considered for dependencies:

1. **Keep `requirements.txt` / `requirements-dev.txt`** — familiar, but no lockfile, no declared Python version, and two files to keep consistent.
2. **pip-tools** — adds a lockfile, but another tool to install and a compile step to remember.
3. **Poetry** — full-featured, but heavier, with its own metadata format and slower resolution.
4. **uv** — one fast tool that manages the Python version, a standard `pyproject.toml`, a cross-platform lockfile and the virtual environment. Dev dependencies are a standard dependency group ([PEP 735](https://peps.python.org/pep-0735/)).

Options considered for enforcing quality: documentation only (relies on goodwill), local hooks only (can be bypassed), or CI only (slow feedback). Hooks and CI are complementary.

## Decision

### Dependencies: uv

- Dependencies are declared in `pyproject.toml`: runtime in `[project].dependencies`, tooling (pytest, ruff, pre-commit, pip-audit) in the `dev` dependency group. Versions stay pinned exactly.
- `uv.lock` is committed and is the source of truth for what is installed. `requires-python` and `.python-version` pin Python 3.13.
- The app is not a package (`package = false`): uv installs dependencies only.
- `requirements*.txt` are removed. Contributors use `uv sync`; the Dockerfile and production hosts use `uv sync --locked --no-dev`.
- `--locked` is used in CI, Docker and production so a stale lockfile fails loudly instead of silently re-resolving.

### Quality gates: the same checks locally and in CI

- **ruff** for lint and format (rule sets: pycodestyle, pyflakes, isort, bugbear, pyupgrade, bandit-style `S`, simplify). One tool replaces flake8, isort, black and a basic security linter. Per-file ignores must carry a justification comment.
- **pre-commit** hooks: ruff and hygiene checks plus a lockfile check on commit; Conventional Commits message check on commit-msg; the full test suite on push; direct commits to `main` blocked.
- **GitHub Actions**:
  - `ci.yml`: lockfile check, lint and format, tests, Docker build, Conventional Commit PR title.
  - `security.yml`: `pip-audit` on the locked runtime dependencies, CodeQL, gitleaks; also weekly.
- **Dependabot** opens weekly PRs for uv dependencies and GitHub Actions, monthly for the Docker image. These go through the same CI.

Hooks give fast feedback; CI is the enforcement point because hooks can be skipped with `--no-verify`.

### Amendment (2026-11-05): hooks live in this repo

The first version of the pre-commit config pulled hooks from four third-party repositories pinned by tag. A tag can be moved, and each hook runs arbitrary code on every contributor's machine at every commit, so that was a supply-chain exposure with no lockfile protection.

All hooks are now `repo: local`. Ruff and uv are run from the versions pinned in `uv.lock`, and the file-hygiene checks (whitespace, end-of-file, YAML/TOML validity, conflict markers, large files, private keys, protected branch, Conventional Commit messages) are implemented in `hooks/checks.py` with unit tests. Secret scanning follows the same principle: CI runs the MIT-licensed gitleaks CLI directly, pinned to a version and verified against a SHA-256 checksum, rather than the `gitleaks-action` wrapper, which needs a paid licence key for organisation-owned repositories. Two known false positives (a fixed test-only encryption key) are allowlisted by exact fingerprint in `.gitleaksignore`.

The only third-party code involved is what is already locked as a dev dependency (including `pyyaml` for the YAML check). Trade-off: we now maintain about 150 lines of hook code, and the private-key check is a simple pattern match rather than a maintained rule set; CI's gitleaks job remains the thorough secret scan.

### Deliberate choices

- **`pip-audit` is report-only** (`continue-on-error`) until the advisories against the currently pinned `cryptography` and `pytest` versions are resolved. Making it blocking now would fail every PR for reasons unrelated to the change. It should be made blocking once the pins are updated.
- **Conventional Commits** are required so history is readable and changelogs can be generated later.
- **The pre-push hook runs the whole suite** (about 90 seconds). That is slow, but it is the last local check before CI and keeps broken pushes off shared branches.
- **No type checker yet.** The codebase has little annotation; adding mypy or pyright now would produce noise rather than signal. Revisit as annotations grow.
- **No coverage threshold yet.** A percentage target invites gaming; revisit once there is a baseline.

## Consequences

**Positive**

- Installs are reproducible across contributors, CI, Docker and production.
- Style discussion is removed from review; formatting is automatic.
- Common security mistakes, leaked secrets and vulnerable dependencies are surfaced on every PR.
- A new contributor needs one tool (`uv`) and two commands to be set up.

**Negative**

- Contributors must install uv. It is a single binary and documented in the README, but it is one more prerequisite than `pip`.
- Hooks and CI add time to commits, pushes and PRs.
- The first ruff run reformatted much of the codebase, so `git blame` for that commit is noisy. It can be hidden with `git config blame.ignoreRevsFile` if desired.
- Dependabot and the lockfile add routine PRs that need review.

**Follow-ups**

- Make `pip-audit` blocking once the known advisories are cleared.
- Require the CI jobs as branch protection on `main` in repository settings.
- Consider a type checker and a coverage floor.

See [docs/development.md](../development.md) for how to use the workflow day to day.
