# e2e: end-to-end tests for the demo scenario (I2)

Playwright tests that replay `docs/scenario-demo.md` in the web interface — map and 3D view —
plus an offline test and an automatic accessibility audit (axe-core).
Gaps found during the last run are listed in [`ECARTS.md`](ECARTS.md).

## Running

Prerequisites: `make install` at the repo root (Python with uv, front with pnpm).

```bash
cd e2e
pnpm install --ignore-workspace
pnpm exec playwright install chromium   # once
pnpm test                                # single run
pnpm test:3x                             # three runs in a row, each on a fresh API
pnpm report                              # HTML report from the last run
```

Playwright launches the API itself (port 8100, no database) and the production front served
by `vite preview` (port 4173). A production build is required for the offline service worker.

| Variable | Effect |
| --- | --- |
| `E2E_SITE=jezero` | Runs the scenario on Jezero (the package must be installed under `data/packages/`) |
| `E2E_REUSE=1` | Reuses an API and front already running on ports 8100 and 4173 |
| `E2E_SKIP_BUILD=1` | Serves `web/dist` without rebuilding |
| `E2E_API_PORT`, `E2E_WEB_PORT` | Alternative ports |

The API keeps targets, plans, EVAs and alerts in memory: one run mutates that state (a target
deleted, an eruption played). `pnpm test:3x` therefore restarts the servers for each run,
as CI does.

## Contents

| File | Role |
| --- | --- |
| `tests/scenario.spec.ts` | The 14 scenario steps, one per test, played in order on the same page |
| `tests/hors-ligne.spec.ts` | Network cut during use, reopening without network (ENF-01) |
| `tests/accessibilite.spec.ts` | axe-core, WCAG 2.1 A and AA, map and 3D, dark and daylight themes (ENF-06) |
| `tests/helpers.ts` | App opening, target reset, screen position of a geographic point |
| `ECARTS.md` | Gap report: what does not pass, why, and who fixes it |

## Gaps and `fixme`

A step that the application does not yet support is marked `test.fixme(true, "Gap En …")`:
it is skipped, the rest of the scenario continues, and the report shows it. The test body
already describes what to verify. When the gap is fixed, remove the `fixme` line and rerun.

The accessibility audit tolerates violations listed in `KNOWN` (one rule and one pattern per
gap) and fails on any other. It attaches the full axe report for each view to the result.

## Measurements recorded by the tests

Each run annotates the HTML report with:

- the time between target modification and display of the three variants (EF-05, limit 5 s);
- the delay between WebSocket alert receipt and banner display (limit 1 s);
- the dose rates received during the simulated eruption.

## Continuous integration

The "Demo scenario" job (`.github/workflows/e2e.yml`) builds the front once, then runs the
suite three times in a row, each on a fresh API, without retries. The HTML reports from all
three runs are attached to the job.
