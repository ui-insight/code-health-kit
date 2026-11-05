# code-health-kit

The parts of code-health measurement that have to live inside each project.
It gives University of Idaho software projects CI gates that keep code from
getting harder to maintain, and publishes the measurements that only a
project's own CI can take.

It is a kit you add to an existing repository, not an app template. It works
with whatever template or stack a project started from.

## Where this fits

Code health is measured in two places:

| Measured | Where | Why there |
|---|---|---|
| Complexity limits, coverage floor, secret scan | **In each project**, with this kit | They stop problems while someone is working. Coverage needs the project's tests to run, which only its own CI can do. |
| Lines of code, complexity and maintainability distributions, duplication, dependency health, churn, hotspots, which gates exist | **Independently**, by the collector in the Distributed Debt Ledger | One pinned set of tools for every project keeps numbers comparable. Different linters score the same code differently, so a project's own linter can't be compared with another's. |

This kit feeds the collector two things: the `.code-health.toml` manifest and
a coverage summary artifact. The collector's results appear on the IIDS
portfolio site as summary numbers.

## What's in the kit

| Path | What it is |
|---|---|
| `actions/manifest` | CI step: checks `.code-health.toml` is valid. |
| `actions/coverage` | CI step: enforces a coverage floor and uploads a normalized coverage summary as an artifact. |
| `actions/complexity-caps` | CI step: fails when a Python function exempted with `# noqa: C901` goes over its `complexity-cap:`, has no cap, or no longer needs the exemption. |
| `actions/secret-scan` | CI step: scans git history for committed credentials with a pinned, checksum-verified gitleaks. |
| `templates/` | Starting configs to copy: the manifest, the Ruff complexity block and the ESLint per-file caps pattern. |
| `scripts/bootstrap_caps.py` | Measures an existing project and prints the caps it needs to adopt the complexity limit. |
| `scripts/check_complexity_caps.py` | The check behind `actions/complexity-caps`; runs locally too. |
| `docs/manifest.md` | The manifest specification. |

The CI steps are composite actions, so they slot into a project's existing jobs
rather than replacing them.

## Adopting it

**1. Add the manifest.** Copy `templates/code-health.toml` to the repository
root as `.code-health.toml`, set `project` to the portfolio slug, and list the
components. Check it locally:

```sh
python3 path/to/code-health-kit/scripts/check_manifest.py .
```

**2. Add the complexity ratchet.** Run the bootstrap script against the
project, then paste what it prints into `pyproject.toml` and
`eslint.config.js` using the patterns in `templates/`:

```sh
python3 path/to/code-health-kit/scripts/bootstrap_caps.py --python backend --eslint frontend
```

Python functions over the limit get `# noqa: C901  complexity-cap: N` on their
def line, and TypeScript files over the limit get a per-file cap. Either way the
cap is today's score.

**3. Add the CI steps.** Put the manifest and secret-scan steps in any job, and
the coverage step after each test run:

```yaml
jobs:
  code-health:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0          # the secret scan reads the whole history
      - uses: ui-insight/code-health-kit/actions/manifest@v1
      - uses: ui-insight/code-health-kit/actions/secret-scan@v1

  backend:
    # ...existing setup and install steps, including the project's own Ruff...
      - uses: ui-insight/code-health-kit/actions/complexity-caps@v1
        with:
          working-directory: backend
      - run: pytest --cov=app --cov-report=xml
      - uses: ui-insight/code-health-kit/actions/coverage@v1
        with:
          component: backend
          report: backend/coverage.xml
          min: 78

  frontend:
    # ...existing setup and install steps...
      - run: npx vitest run --coverage --coverage.reporter=json-summary
      - uses: ui-insight/code-health-kit/actions/coverage@v1
        with:
          component: frontend
          report: frontend/coverage/coverage-summary.json
          min: 60
```

Set each `min` a little below today's coverage, then raise it as tests are
added. Coverage reports must be Cobertura XML (pytest-cov, coverage.py) or an
Istanbul `json-summary` (Vitest, Jest). Vitest needs `@vitest/coverage-v8`
installed.

## Tightening over time

- When a refactor brings a file under its cap, lower the cap. Delete it once it
  reaches the default. Run `bootstrap_caps.py` again to find caps that are
  higher than they need to be.
- Python works the same way, through `complexity-cap:` on each `# noqa: C901`
  marker. The complexity-caps step fails when a function goes over its cap or
  has a marker without one. It leaves a note when a cap can be lowered, and it
  fails once a function is back within the limit, so its marker gets removed.
- Raise a coverage `min` after adding tests.

## Versions

Projects pin a major version (`@v1`). Fixes and additions that don't break
existing projects move the `v1` tag; anything that would break a project's CI
gets `v2`.

## Developing the kit

```sh
python3 -m pip install pytest
python3 -m pytest
```

The kit's own CI runs these tests and uses its own actions on this repository.
