# Demo scenario gap report (I2)

Recorded on 15 November 2026 by replaying `docs/scenario-demo.md` in Chromium on the
fictif site, production front (`vite build` then `vite preview`), fresh API without database.
Each gap has a number referenced in the tests: a step blocked by a gap is marked
`test.fixme("Gap En …")`, and the accessibility audit tolerates the violations listed here
one by one. Fixing a gap means also removing its `fixme` (or its line from `KNOWN` in
`tests/accessibilite.spec.ts`) so the test verifies it.

## Status per step

| # | Step | Status | Gap |
| --- | --- | --- | --- |
| 1 | Open Marswalk on the site | ✓ | |
| 2 | Safety preset | ✓ | |
| 3 | Click on the dune edge | ✓ after fix E1 | |
| 4 | Hazard zones | ✓ | O3, O4 |
| 5 | Scientific objective | ◐ per-target objective only | E2 |
| 6 | Plan three targets | ✓ 2.7 s between target deletion and variant display | |
| 7 | Compare variants | ✓ after fixes E4, E5, E6 | |
| 8 | Chosen variant profile | ✓ profile and table synchronised; map marker: see "Not verified" | |
| 9 | 3D view | ◐ exaggeration adjustable, flyover broken | E7 |
| 10 | EVA and virtual astronaut | ✓ after fix C1 | |
| 11 | Obstacle and observation | ✓ after fix E3 | |
| 12 | Solar eruption | ✓ alert displayed 0.4 s after receipt | |
| 13 | Acknowledge the alert | ✓ | |
| 14 | Forced return, GeoJSON logbook | ✓ new EVA after eruption: fixed (E8) | |
| — | Offline (ENF-01) | ✓ offline reopen: fixed (E9) | |
| — | Accessibility (axe, WCAG 2.1 AA) | ◐ | E10, E11 |

## Fixed with these tests

**C1. The simulated EVA rejected every computed plan.** `POST /api/eva` returned "Plan not
found" for any plan from `POST /api/sites/{site_id}/plans`: the simulator (A4) only read
`plan-demo`, as announced in `tasks/change-requests/A4-source-des-plans.md`. No EVA could
start from the UI, and the GeoJSON plan export (X1) failed likewise. Fix: `get_simulator()`
first reads the A2 plan repository (PR `fix/I2-integration`), with a test in
`api/tests/a4/test_plans_a2.py`.

**C2 (E4). An unreachable target is excluded and announced.** Before routing, P2 identifies
targets that no sequence of walkable cells connects to the start
(`_p2/reach.py`): they are removed from the variant with the warning
"Target '…' excluded: no walkable path from the start (straight line crosses a 65° slope)".
Safety net: any segment that fell back to the straight-line emergency path is flagged in
`warnings`, and `return_check` moves to `fail`. The fictif site now has a ~200 m ramp
(max slope ≈ 13°) west of the habitat; the Delta Front is reached via this detour.
Tests: `planner/tests/p2/test_ecarts_i2.py`, step 7d.

**C3 (E5). Smoothing erased detours.** String-pulling only checked forbidden cells: it
straightened any cost-driven detour, and all three variants fell back to the same straight
line. A shortcut is now retained only if its cost is no higher than the raw path (exact cost
integral along the segment). Routing no longer cuts corners of forbidden cells.
On fictif: 3,193 m (safest, max slope 15°), 2,917 m (fastest, 19°), 3,158 m (science).
Step 7c.

**C4 (E6). One sentence per segment.** The explanation compares the trace to the straight
line between its endpoints: "Bypasses a 65° slope: +518 m (max slope 15.0° on the trace).",
"Goes straight (max slope 4.0° on the trace, crosses loose soil).". Passing through a mineral
unit is only cited for the science variant. Same text for the local recalculation during the
EVA (A4). Step 7b.

**E1 fixed. A map click queries the point (step 3).** The shell now broadcasts each MapLibre
click via `shared/mapClick.ts` (workaround for `tasks/change-requests/F2-pickmode-map-click.md`,
without touching the frozen store); `QueryPanel` subscribes to it in query mode and defaults
to the manifest habitat. The click is captured on MapLibre, so it fires even over a target or
zone; in query mode, F2 no longer selects the clicked target. Verified by step 3, which also
checks the first request at the habitat.

**E3 fixed. Obstacle and observation during the EVA (step 11).** "Field survey" panel (F7),
shown under "Safety" while an EVA is tracked: "Report obstacle" posts
`POST /api/eva/{id}/obstacles` 50 m ahead of the astronaut on the route (radius 6 m);
"Log observation" posts at the current position and, without network or on failure, goes
through `useOfflineQueue().enqueue("addObservation", …)` with the EVA id. Replay is now
kept at module level, so an operation is not replayed by every panel using the queue.
Verified by step 11; step 14 checks that obstacle and observation are in the GeoJSON logbook.

## Open gaps

Severity: **critical** = safety risk in the presentation; **high** = a demo step cannot be
played; **medium** = the step plays but does not show what the scenario says; **low** = polish.

### E2. No site science panel (step 5) · medium · S1, F2

The scenario expects a panel justifying the site and targets with NASA data (delta, clays and
carbonates, olivine). The UI only shows each target's objective in its card;
`docs/science/jezero.md` is not surfaced anywhere.

**Fixed** (branch `fix/I2-ecarts-science-finitions`): "Site science" panel in the left column
(F2, `SciencePanel.tsx`), summary of `jezero.md` with its sources; test 5b is no longer `fixme`.

### E3. No obstacle report or observation in the UI (step 11) · high · F4, F7, X1

The API can do it (`POST /api/eva/{id}/obstacles`, `POST /api/eva/{id}/observations`) and F7's
offline queue knows how to replay `addObservation`, but no button calls them. Step 11 and the
"even offline" part of the scenario are not shown. To do: two actions in the EVA panel, the
observation going through `useOfflineQueue().enqueue("addObservation", …)`.

### E4. Without a walkable path, the trace silently crosses the cliff (steps 7 and 10) · critical · P2, T00 (fictif site) · **fixed**

On the fictif site, the plateau cliff spans the full width: the Delta Front is unreachable,
A* finds nothing and `_plan_segment` falls back to the straight emergency line. All three
variants cross a 65° slope, without warnings (`warnings` is empty despite the code claiming
otherwise) and with "✓ Return 90%". During the EVA the virtual astronaut climbs the cliff and
triggers the "Slope too steep, 43°" alert. To do: (1) P2 flags every emergency-line segment
in `warnings` and `return_check`, or rejects the target; (2) the fictif site opens a walkable
passage to the plateau so the CI demo shows a real detour. Also check on Jezero.

### E5. All three variants are identical (step 7) · high · P2, I1 · **fixed**

Same trace, same distance, same duration for "safest", "fastest" and "science" on the fictif
site, including on reachable segments. E4 explains part of it, not all. To revisit with weights
tuned by I1.

### E6. Explanations do not state the reason for the detour (step 7) · medium · P1, P2, F2 · **fixed**

The scenario expects "bypasses a 24° slope". The UI displays cost-cell terms for the midpoint
of the segment: "traversal time 2.36 s (Tobler 0.38g × soil factor) → contribution 1.181 · R=0.000 …".
To do: one plain-language sentence per segment derived from the deviation from the direct trace
(slope avoided, obstacle bypassed, penalized zone).

### E7. The 3D flyover stops immediately after launch (step 9) · medium · F6

`useTerrain3dData` rebuilds `activeProfile` on every render; the `useFlyover` effect that
resets the flyover "when the route changes" fires on every render and sets `playing` back to
false. One-line fix: `useMemo` on `activeProfile`.

**Fixed**: `activeProfile` and `terrainConfig` memoised in `useTerrain3dData`; test 9b is
no longer `fixme`.

### E8. After the eruption, any new EVA stops in place (after step 14) · high · A3, A4

Danger alerts raised by the `solar-event` scenario remain active (without an attached EVA)
after the scenario stops, even when acknowledged, while the dose rate has returned to 16 µSv/h.
Any EVA launched afterwards ends within ten seconds without having moved (0 m). Only an API
restart restores the demo. To do: raise `alert_cleared` when the condition disappears and only
force return for alerts belonging to the current EVA; L1 will need this for its reset command.

**Fixed** (PR `fix/E8-E9-alertes-hors-ligne`). At the end of a scenario (stopped or elapsed),
A3 raises `alert_cleared` for its site-level alerts ("end of scenario") then re-evaluates real
conditions (`AlertEngine.clear_scope`). A4 no longer forces return for a site-level alert
already acknowledged before the EVA started. Verified by test 14b and two tests in
`api/tests/a4/test_simulator.py`.

### E9. No service worker: the application does not reopen offline (ENF-01) · high · F7

`web/src/features/offline/vite.ts` loads `vite-plugin-pwa` via `require`, which does not exist
in the ESM Vite configuration; the error is swallowed by the `catch` and the plugin is never
added. The build produces neither `sw.js` nor a manifest, nothing is cached. The network badge
and already-loaded data hold up, but a reload without network gives a blank page. To do:
`import { VitePWA } from "vite-plugin-pwa"` at the top of the file.

**Fixed** (PR `fix/E8-E9-alertes-hors-ligne`). ESM import; the build produces `sw.js` and
`manifest.webmanifest`. Three adjustments follow: the main bundle (3 MB) exceeded the 2 MB
pre-cache limit, the `/api/` and `/tiles/` patterns were RegExps that Workbox compares against
the full URL (nothing was cached), and `index.html` now serves as the navigation fallback.
Test "The application reopens without network" waits for the map to load before cutting the
network. Remaining: the `icon-192.png` and `icon-512.png` manifest icons do not exist in
`web/public` (no effect on offline).

### E10. State colors written as text with insufficient contrast · medium · T00 (tokens), F2, F3, F4

Green "Normal" #009e73, orange #e69f00 and vermilion #d55e00 are used as text color. Contrast
ratio: 4.45:1 on the dark theme, 2.3–3.9:1 on the "daylight" theme, instead of the required
4.5:1. The light theme, intended for readability in direct sunlight (ENF-06), is most affected:
safety panel gauges, variant "Return" labels, profile legend, weather table. To do: a darker
variant of each state color for text use, keeping the vivid color for dots and traces.

**Fixed**: tokens `--text-ok`, `--text-caution`, `--text-danger`, `--text-info` per theme
(at least 4.8:1 on all surfaces), `textColors` on the JS side, black text on orange and
vermilion dots; line removed from `KNOWN`.

### E11. `aria-label` on a `div` without a role in the 3D view · low · F6

The `.inset-0` element of the 3D render carries an `aria-label` that is invalid without a
role. Add `role="img"` (or remove the label; the canvas already carries one).

**Fixed**: `role="img"` added; line removed from `KNOWN`.

## Observations without a dedicated test

- **O1. Missing accents in map labels.** "Unité à olivine" renders as "Unit    olivine": the
  deck.gl label font lacks accented characters (F2). **Fixed**: `characterSet: "auto"` on F2's `TextLayer` instances.
- **O2. Local recalculation after edge-case obstacle.** `api/tests/a4/test_demo.py` measures
  2.0 s in the cloud container (failure at 2,004 ms against a 2,000 ms limit, unrelated to fix
  C1); I1 measured 2.9 s on Jezero against a 2 s target. Green in GitHub CI.
- **O3. Forbidden zones in vermilion, not red.** The scenario says "red"; the colorblind-safe
  palette uses vermilion #d55e00 with the ⛔ icon. Defensible choice; align the scenario text.
- **O4. Zone cause is always "slope".** `GET /hazards` only returns zones with cause `slope`
  on the fictif site; scarps and obstacles are not cited as causes.
- **O5. All API state lives in memory.** Targets, plans, EVAs and alerts do not go through
  PostGIS: a restart wipes everything, and two processes share nothing. Tests therefore start
  from a fresh API on each run; L1 will need to account for this.
- **O6. `uv.lock` out of date.** `uv run` without `--frozen` rewrites it (adds matplotlib
  and its dependencies). CI uses `--frozen` and is unaffected.

## Not verified automatically

- Profile-to-map synchronisation (step 8): the marker is drawn on the WebGL canvas. Tests
  verify the profile and segment table; the map marker remains a visual check.
- Visual rendering of layers, traces and 3D: tests verify that canvases display and that data
  arrives, not the actual image.
- Jezero: tests run on the fictif site in CI. They can be run on Jezero with
  `E2E_SITE=jezero` on a machine where the package is installed.
