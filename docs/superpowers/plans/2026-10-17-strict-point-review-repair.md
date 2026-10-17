# Strict point review repair implementation plan

Goal: make strict plans progress from prepared points through automatic/manual areas and accepted review to Render.
Architecture: focused area adapter and metadata; strict diagnostics in motion/staging; an isolated areas stage; editor list/status/canvas controls.
Spec: [strict point review repair design](../specs/2026-10-17-strict-point-review-repair-design.md).

## Tasks

- [x] Add regression tests for strict missing/stale diagnostics and area generation; run them red, then implement the smallest motion/area contract.
- [x] Add stage and queue tests for `areas`; run red, then isolate it to Load Image and the motion editor.
- [x] Add editor tests for materialized group lists and mode persistence; run red, then implement the controls.
- [ ] Add pinned SAM installer support and recovery tests without changing Torch.
- [ ] Reconcile docs/codemap; run Python, Node, diff and editor fixture checks.

## Execution ledger

- Red: `python -m unittest tests.test_areas tests.test_motion.MotionTests.test_strict_review_names_each_missing_or_stale_area -v` failed because `comfy_ltx_loop.areas` did not exist. `node --test tests/test_stages.mjs` failed with `Unknown stage areas`.
- Green: the same Python command passed 3 tests after the isolated adapter and strict point diagnostics; `node --test tests/test_stages.mjs` passed 8 tests after stage pruning admitted `areas`.
- Red: `node --test tests/test_editor_semantics.mjs` failed its new materialized-list assertion: a populated character group displayed its empty instruction.
- Green: focused Python motion/area/stage tests passed 46 tests; focused editor/stage/queue Node tests passed 29 tests. The final full-suite and fixture results are recorded after their fresh runs.

## Qualification boundary

The absent latent-mask adapter remains a separate renderer task. Local tests and the simulated editor fixture do not prove installed ComfyUI conversion, actual SAM/Qwen GPU release, inference, or visual quality.
