# Strict motion areas implementation plan

Goal: add compatible Free motion and reviewed Only pointed parts protection.
Architecture: normalize strict masks and review state in `motion.py`; composite protected pixels in `candidates.py`; pass the source through staging; expose clear editor point controls.
Spec: [strict motion areas design](../specs/2026-10-17-strict-motion-areas-design.md).

## Tasks

- [x] Add failing motion-plan tests for mode defaults, strict authorization, identifiers, areas and stale reviews; implement the smallest contract.
- [x] Add failing candidate tests for exact protected pixels; persist source and compose after crop/resize/finish.
- [x] Add failing stage/editor tests for strict empty rejection, source wiring and the two add buttons; implement backend/UI behavior.
- [x] Update workflow source wiring, docs and codemap; run focused Python/Node suites and diff check.

## Execution ledger

- Red: `python -m unittest tests.test_motion -v` produced the expected missing
  `render_mode` error and absent strict-review failure. Green: the same command
  passed 19 tests after normalized render modes, IDs, masks and fingerprints.
- Red: `python -m unittest tests.test_candidates.CandidateTests.test_strict_candidate_restores_protected_source_pixels_exactly -v`
  errored because `save_candidate` had no `source` argument. Green: it passed after
  source/mask artifacts and exact zero-mask compositing were added.
- Red: `python -m unittest tests.test_stages.StageTests.test_strict_render_rejects_direct_no_point_render_with_actionable_message -v`
  errored on the missing render-mode contract. Green: it passed with the required
  strict no-point message.
- Red: `node --test tests/test_editor_semantics.mjs` failed because the old selector
  and Add point button remained. Green: 11 tests passed after the two explicit add
  buttons replaced them.
- Focused compatibility: `python -m unittest tests.test_motion tests.test_candidates tests.test_stages -q`
  passed 57 tests. `node --test tests/test_motion_workflow.mjs` passed 5 tests and
  all Node tests passed 43 tests. `git diff --check` passed (line-ending notices only).
- A full Python discovery run was started twice. The runner exceeded the interactive
  capture window while its raster/integration subprocesses ran; its final exit text
  was not captured in this session. Do not treat it as full-suite evidence; rerun it
  on the target host before declaring the change locally qualified.

## Remaining scope and qualification gap

The persisted source-mask contract and post-decode/finish protection are implemented.
The requested SAM 2.1 Small installation/proposal path, paint/erase area editor, and
connected latent mask adapter have not been added. Strict rendering therefore must not
be deployed as renderer-qualified: local source compositing proves PNG protection only,
not latent masking, installed graph conversion, model resource release, GPU inference
or selected-part visual quality.
