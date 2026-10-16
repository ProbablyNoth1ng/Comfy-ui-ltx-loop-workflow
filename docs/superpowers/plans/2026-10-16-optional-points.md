# Optional points implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline. Steps use checkboxes for tracking.

**Goal:** Render with either, both or no active point groups while preserving text guidance and saved points.

**Architecture:** Motion plan booleans control active tracks and review. The stage node creates a fresh no-point plan when no active points exist. The editor switches serialize those booleans and relax the queue gate only for no-point Render.

**Tech stack:** Python unittest, Node test runner, existing ComfyUI LTX Motion Track graph.

**Spec:** [Optional points design](../specs/2026-10-16-optional-points-design.md).

## Global constraints

- Keep official workflow baseline and existing CLI unchanged.
- Older plans default both point groups on.
- Empty background text excludes background tracks but nonblank text still guides motion.
- Distinguish local fixture evidence from installed ComfyUI and GPU evidence.

## Review focus

- Saved points in switched-off groups remain editable and survive reopen.
- Re-enabled stale groups cannot borrow an old accepted review.
- A stale active group still blocks Render.
- No-point Render cannot invoke Qwen or leak another stage into its graph.
- A no-point candidate records `not_required` review.

### Task 1: Motion plan contract

**Files:** `comfy_ltx_loop/motion.py`, `tests/test_motion.py`.
**Interfaces:** `use_character_points` and `use_background_points` plan booleans; `canvas_tracks`, `review_plan`, `require_review` consume them.

- [x] Write tests for four combinations, legacy defaults and active-group preparation/review.
- [x] Run `python -m unittest tests.test_motion -v`; record expected behavioral failures.
- [x] Implement group filtering and active-group review rules.
- [x] Rerun targeted tests and record results.

### Task 2: Backend Render

**Files:** `comfy_ltx_loop/staged_comfy.py`, `tests/test_stages.py`.
**Interfaces:** optional node inputs `use_character_points` and `use_background_points`; no-point render emits `[]` and a plan with `review.state=not_required`.

- [x] Write tests for direct Render, text guidance and retained disabled points.
- [x] Run `python -m unittest tests.test_stages -v`; record expected failures.
- [x] Implement no-point render and active-point validation.
- [x] Rerun targeted tests and record results.

### Task 3: Editor and workflow

**Files:** `comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js`, `tests/test_editor_semantics.mjs`, `tools/build_comfy_ltx_loop_workflow.mjs`, `workflows/comfy-ltx-loop-motion.json`.
**Interfaces:** editor switches synchronize plan booleans; queue permits direct no-point Render.

- [x] Write editor tests for switch, reopen and direct queue behavior.
- [x] Run `node --test tests/test_editor_semantics.mjs`; record expected failures.
- [x] Implement controls, queue gate and workflow hint.
- [x] Rerun targeted tests and record results.

### Task 4: Verification and handoff

**Files:** `docs/product-spec.md`, this plan, its design, `docs/qualification.md`, `codemap.md`.

- [x] Run final Python and Node suites, `git diff --check`, and editor fixture.
- [x] Reconcile acceptance criteria, update delivery evidence and codemap.
- [x] Inspect the final diff; report remaining installed ComfyUI/GPU/visual gaps.

## Red/green ledger

- Motion: `python -m unittest tests.test_motion -v` initially failed four expected
  group-filter/preparation assertions; after implementation 16 tests passed.
  The later saved-background activation regression failed as expected, then passed.
- Backend: `python -m unittest tests.test_stages -v` initially errored on direct
  Render and missing group inputs. No-point implementation made the new tests pass;
  the old stale-review test was updated to exercise an active stale plan.
- Editor: `node --test tests/test_editor_semantics.mjs` initially failed two
  assertions for missing switches and blocked direct queue; then 8 tests passed.
- Candidate: the new persistence test initially failed because no fingerprint was
  present; it passed after the `not_required` exception was limited to no tracks.
- Re-enabling points after text-only Render initially lost preparation stamps;
  `test_direct_render_preserves_preparation_history_for_reenabled_points` failed,
  then passed after preserving stamps with saved points.
- Workflow default booleans: `node --test tests/test_motion_workflow.mjs` first
  failed because the editable workflow lacked the two widget values; after
  regeneration all five tests passed. The official baseline diff is empty.
- Targeted post-change: 48 Python tests and 40 Node tests passed. The first full
  Node run found an unrelated stale rebrand expectation in `test_queue_control.mjs`;
  its assertion now uses the actual Comfy LTX Loop name and the rerun passed.
- Editor fixture: `python tests/editor_harness.py` started and GET `/` returned
  HTTP 200. It uses simulated queues and does not prove installed frontend behavior.
- Final verification: `python -m unittest discover -s tests -q` passed 98 tests;
  the Node suite passed 40 tests; `git diff --check` exited 0. The maintained
  tree was reconciled against `rg --files --hidden` with codemap exclusions.
