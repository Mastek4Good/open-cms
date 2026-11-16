# Running Costs

What this system costs to run, what could start costing money, and the
decisions that keep it free. Written for a charity budget: the working
assumption is that every recurring cost must be justified or removed.

Verified against the live repository and GitHub's billing documentation on
2026-11-09. The GitHub figures change; re-check them before relying on the
exact numbers.

## Summary

Nothing in this repository currently bills. That is a consequence of two
facts, and it stops being true if either changes:

1. The repository is **public**.
2. The `Mastek4Good` organisation is on the **free** plan.

The only paid external service wired into the application is what3words.

## What is free, and why

| Feature | Why it costs nothing |
|---|---|
| All CI and security workflows | Standard GitHub-hosted runners are free for public repositories and draw down no compute allowance. All 17 jobs run on `ubuntu-latest`. |
| CodeQL (python, javascript-typescript) | Code scanning is free for public repositories — $0 per committer. It is the paid GitHub Code Security feature only on private repositories. |
| Secret scanning (gitleaks) | Runs the MIT-licensed gitleaks **CLI** with a pinned checksum, not the `gitleaks-action` wrapper, which needs a paid licence key for organisation-owned repositories. |
| Dependabot | Free on all repositories. |
| GitHub-native secret scanning | Free for public repositories, and currently disabled in repository settings in any case. |
| Docker build job | Builds with `push: false` and a GitHub Actions layer cache. Nothing is stored in a registry. |
| Lighthouse report artifacts | Artifact storage is free for public repositories. |

There are no repository-level Actions secrets, so no paid-service credentials
are available to CI.

## Where money can actually leak

### 1. what3words API — the only paid external service

`W3W_API_KEY` drives `POST /location/autosuggest`
(`app/services/w3w_service.py`). The service is on the what3words **Free**
plan, which covers the AutoSuggest endpoint only. See
[ADR-001](../adrs/001-what3words-integration.md).

The browser is well behaved — `app/static/js/app.js` debounces input by 300 ms
and will not call until the address has two words and the first character of
the third. **The server endpoint has no such protection:** there is no rate
limiting anywhere in the application (no `flask_limiter`) and no caching of
identical lookups. Any signed-in client can call it in a loop and exhaust the
quota.

Amplifier to be aware of: if the shared demo account is enabled in production
it accepts any 6-digit MFA code, and its development password appears in
`.env.example` in a public repository. `ALLOW_DEMO_IN_PRODUCTION`,
`DEMO_ACCOUNT_ENABLED` and `DEMO_ACCOUNT_SHARED_MFA` all default to `False` in
`ProductionConfig`, so this only applies to a deliberately enabled demo. See
[ADR-009](../adrs/009-shared-demo-account.md).

### 2. Hosting the transcription service

Transcription is a self-hosted `whisper.cpp` container
(`services/transcriber`, reached via `TRANSCRIPTION_URL`), not a paid
speech-to-text API. There is no per-minute transcription fee. The cost is
whatever the long-running container is hosted on. This is the cheap choice
and should stay that way — moving to a hosted STT API would introduce a
per-use bill.

### 3. AI-powered scanning features

Copilot Autofix and AI-assisted pull request scanning bill against AI credits
even where the underlying scanner is free. The current setup uses plain
advanced-setup CodeQL workflows with none of these enabled. Do not accept a
prompt to "turn on default setup" without checking what it enables.

## The cliff: going private

If this repository is ever made private, three costs start at once:

- **Actions compute becomes billable.** GitHub Free for organisations includes
  $12 per month of compute; a standard 2-core Linux runner is $0.006 per
  minute, so roughly 2,000 minutes. The current suite runs around nine jobs
  per pull request, two of them CodeQL analyses.
- **CodeQL stops working** without a GitHub Code Security licence, charged per
  committer.
- **Artifact and cache storage** starts counting against the allowance.

Treat repository visibility as a cost decision, not only an openness one.
Larger runners are the other cliff — they are *not* free on public
repositories, so keep every job on `ubuntu-latest`.

## Open actions

- [ ] Rate-limit and cache `POST /location/autosuggest`. This is the only live
      spend risk in the application.
- [ ] Record the "stay public" constraint in
      [ADR-010](../adrs/010-uv-and-automated-quality-gates.md), so nobody
      flips visibility without seeing the consequence.
- [ ] Optionally set `retention-days` on the Lighthouse artifact upload. Free
      today; keeps the footprint honest if visibility ever changes.

## A note on removing checks to save money

CodeQL and gitleaks were considered for removal on cost grounds. Neither costs
anything in this configuration, and between them they flag real findings, so
removing them would save nothing and lose signal. If they are ever removed it
should be for a different reason — CI noise or run time — recorded as such.

## Sources

- [GitHub Code Quality pricing](https://github.com/features/code-quality)
- [GitHub Advanced Security plans](https://github.com/security/plans)
- [About the CodeQL CLI](https://docs.github.com/en/code-security/codeql-cli/getting-started-with-the-codeql-cli/about-the-codeql-cli)
- [GitHub Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions)
- [Actions runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing)
- [Product usage included with each plan](https://docs.github.com/en/billing/reference/product-usage-included)
