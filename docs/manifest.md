# The `.code-health.toml` manifest

The manifest sits at a repository's root and says which code the project wrote,
which code is tests, and which code is generated or vendored. The independent
collector in the Distributed Debt Ledger reads it before counting lines,
complexity or duplication, so every project is measured on its own authored
code without anyone writing exclusion notes by hand.

The format is TOML so that Python 3.11+ can read it with the standard library.
`scripts/check_manifest.py`, and the `actions/manifest` step that runs it, check
everything below.

## Keys

| Key | Required | Meaning |
|---|---|---|
| `schema` | yes | Always `1` for this version. |
| `project` | yes | The project's slug on the IIDS portfolio site (`slug` in AISPEG's `lib/portfolio.ts`). This is how measurements are matched to the right project. |
| `[[component]]` | at least one | A separately built part of the repository, such as a backend and a frontend. |
| `component.name` | yes | Lowercase, digits, `-` or `_`. Unique. The coverage step uses the same name. |
| `component.language` | yes | `python`, `typescript`, `javascript`, `r`, `sql` or `shell`. |
| `component.source` | yes | Directories or globs holding authored code. |
| `component.tests` | no | Directories or globs holding test code. Tests may sit inside `source`, as many frontend tests do; the collector counts them as tests, not source. |
| `[exclude]` | no | Code inside `source` that the project didn't write by hand, grouped by why: `generated`, `vendored` or `other`. |

Paths are relative to the repository root. Globs use Python `glob` rules, with
`**` matching any depth. Every entry must match at least one file or
directory, so a stale entry fails the check instead of being silently ignored.

## What the collector does with it

For each component, the collector:

1. takes the files under `source`,
2. removes anything matching `exclude`,
3. sets aside files matching `tests` as test code,
4. measures the rest as authored source.

The collector also skips dependency and build directories (`node_modules`,
`.venv`, `dist`, `build`, `.git`) everywhere, so you don't need to list them.

## Versioning

A breaking change to these rules gets a new `schema` number. The collector will
keep reading schema 1 manifests.
