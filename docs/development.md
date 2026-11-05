# Development workflow

How dependencies, code-quality checks and CI fit together. For forking and
raising a pull request, see [CONTRIBUTING.md](../CONTRIBUTING.md).

## Overview

| Concern | Tool | Defined in |
| --- | --- | --- |
| Dependencies and Python version | [uv](https://docs.astral.sh/uv/) | `pyproject.toml`, `uv.lock`, `.python-version` |
| Lint and format | [ruff](https://docs.astral.sh/ruff/) | `[tool.ruff]` in `pyproject.toml` |
| Tests | pytest | `[tool.pytest.ini_options]` in `pyproject.toml` |
| Local gates | [pre-commit](https://pre-commit.com) | `.pre-commit-config.yaml` |
| Remote gates | GitHub Actions | `.github/workflows/` |
| Dependency updates | Dependabot | `.github/dependabot.yml` |

The reasoning behind these choices is recorded in [ADR-010](adrs/010-uv-and-automated-quality-gates.md).

The same checks run locally (pre-commit) and remotely (CI), so a clean local
run should mean a green pull request.

## Setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then:

```bash
uv sync                      # creates .venv from uv.lock, runtime + dev tools
uv run pre-commit install # installs the git hooks (commit, commit-msg, pre-push)
```

uv reads `.python-version` and downloads Python 3.13 if you do not have it.
`uv sync --no-dev` installs runtime dependencies only (what the Dockerfile and a
production host use).

Run everything through uv: `uv run pytest`, `uv run ruff check .`,
`uv run python main.py`. `uv run` uses the project's `.venv` and first brings it
in line with `uv.lock`, so you never need to activate the environment by hand.
(Activating `.venv` and calling tools directly still works if you prefer.)

## Managing dependencies

Dependencies are declared in `pyproject.toml`:

- `[project].dependencies` — what the app needs at runtime.
- `[dependency-groups].dev` — pytest, ruff, pre-commit, pip-audit.

Versions are pinned exactly. `uv.lock` records the full resolved tree
(including transitive dependencies) and **must be committed**.

```bash
uv add <package>==<version>        # runtime dependency
uv add --dev <package>==<version>  # dev-only dependency
uv remove <package>
uv lock --upgrade-package <name>   # bump one package
uv lock --upgrade                  # bump everything
```

`uv add`/`remove` update both `pyproject.toml` and `uv.lock`. If you edit
`pyproject.toml` by hand, run `uv lock`. There are no `requirements*.txt` files.

The app is not a package (`package = false`): uv installs its dependencies but
not the project itself, and code is run from the repo root.

## Local checks

### Pre-commit hooks

| Stage | Checks |
| --- | --- |
| commit | ruff lint (with autofix) and ruff format; trailing whitespace; end-of-file; YAML and TOML validity; merge-conflict markers; files over 500 KB; private keys; direct commits to `main` blocked; `uv-lock` (lockfile matches `pyproject.toml`) |
| commit-msg | [Conventional Commits](https://www.conventionalcommits.org): `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `build`, `ci`, `chore`, `revert` |
| pre-push | full pytest suite (`pytest -q -x`) |

If a hook fixes files, the commit is aborted. Review the changes, `git add`
them and commit again. Run all hooks on demand with:

```bash
uv run pre-commit run --all-files
```

Hooks can be bypassed with `--no-verify`, but CI runs the same checks and will
fail the pull request.

### Running tools directly

```bash
uv run ruff check .            # lint (add --fix to autofix)
uv run ruff format .           # format (--check to verify only)
uv run pytest -q               # tests
uv run pre-commit autoupdate   # bump hook versions
```

### Ruff

Config lives in `pyproject.toml`: line length 100, target Python 3.13, with
rule sets pycodestyle (`E`, `W`), pyflakes (`F`), isort (`I`), bugbear (`B`),
pyupgrade (`UP`), bandit-style security checks (`S`) and simplifications
(`SIM`). Per-file ignores carry a comment explaining why. Prefer fixing the
code; add an ignore only with a reason.

## Continuous integration

### `ci.yml` — every pull request and push to `main`

| Job | What it does |
| --- | --- |
| Lockfile up to date | `uv lock --check` — fails if `uv.lock` is stale |
| Lint & format | `uv sync --locked`, `ruff check`, `ruff format --check`, hygiene hooks |
| Tests | `uv sync --locked`, `pytest` |
| Docker build | builds the development image (does not push) |
| Conventional PR title | PR titles must follow Conventional Commits |

`--locked` makes CI fail rather than silently re-resolve, so CI always tests
exactly what is in `uv.lock`.

### `security.yml` — pull requests, pushes to `main`, and weekly (Monday)

| Job | What it does |
| --- | --- |
| Dependency audit | `pip-audit` over the locked runtime dependencies. **Report-only** (`continue-on-error`) until currently known advisories are resolved; remove that line to make it blocking |
| CodeQL | static analysis for Python and JavaScript/TypeScript (vendored code excluded) |
| Secret scan | gitleaks over the full history |

### Dependabot

Weekly pull requests for Python dependencies (uv, grouped into one PR) and
GitHub Actions; monthly for the Docker base image. Dependabot updates
`uv.lock` too, so these PRs go through the same CI.

### Suggested branch protection

In repository settings, require the CI jobs (Lockfile, Lint & format, Tests,
Docker build, PR title) to pass before merging to `main`.

## Docker

The `Dockerfile` is for local development only (see the README). It copies uv
from the official image and runs `uv sync --locked --no-dev` into `/opt/venv`
using only `pyproject.toml` and `uv.lock`, so the dependency layer is cached
until those files change.

## Troubleshooting

- **`uv-lock` hook or CI lockfile job fails** — run `uv lock` and commit `uv.lock`.
- **A hook reformatted my files** — expected; `git add` and commit again.
- **`ModuleNotFoundError: app` under pytest** — run from the repo root;
  `pythonpath = ["."]` is configured for pytest.
- **Commit rejected for message format** — use a prefix such as `feat:` or `fix:`.
- **Commit rejected on `main`** — create a branch (`git switch -c my-change`).
