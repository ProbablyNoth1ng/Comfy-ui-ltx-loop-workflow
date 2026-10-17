# Lightweight Qwen point proposals implementation plan

> For agentic workers: use superpowers:executing-plans. Track steps with checkboxes.

Goal: offer 2B point proposals through all existing Prepare actions and install
them alongside the selected larger model.
Architecture: append a mode, reuse Qwen3-VL inference, and add an independently
pinned snapshot to existing install/cache paths.
Tech stack: Python/unittest, Node test runner, Transformers >=5.2,<6.
Spec: [technical design](../specs/2026-10-17-qwen2b-points-design.md).

## Constraints and review focus

Preserve saved strings/slots, defaults, custom paths, isolated stages and official
LTX workflow. Preserve 8B legacy pins and 9B new-install default. Never mark the
whole install successful before 2B completes. Recover interrupted 2B downloads
without resolving moving main again. Use the supplied plan's authorization;
execute in the shared checkout, with no commit, push or deployment requested.
This plan is also the durable execution ledger.

Pre-flight: editor/backend share exact selector `local Qwen3-VL 2B` and bundled
path `models/Qwen3-VL-2B-Instruct`. Installer consumes the repository
`Qwen/Qwen3-VL-2B-Instruct`; it must not replace the larger selection or workflow
defaults. No interface conflict.

## Task 1: editor/backend selection

Files: `staged_comfy.py`, editor JS, `tests/test_stages.py`,
`tests/test_editor_semantics.mjs`, `tests/test_vision.py`.
Interfaces: retain execute signature and widget order; append preparation choice.

- [x] Add tests for option/order, all three Prepare targets, model path mapping,
  model/review invalidation, failure preservation and custom/saved paths.
- [x] Run `python -m unittest tests.test_stages tests.test_vision -q` and
  `node --test tests/test_editor_semantics.mjs`; observe missing-option/dispatch
  and wrong bundled path failures before implementation.
- [x] Append mode to the backend and add the frontend bundled mapping.
- [x] Rerun the same commands; confirm passing behavior.

## Task 2: additive cloud snapshot

Files: `cloud/install.py`, `tests/test_vision_install.py`.
Interfaces: keep larger selection/cache signatures; add separate 2B plan/provenance.

- [x] Add tests for new and legacy installs adding 2B with independent revisions,
  no-download cache reuse, larger switching, interruption and truncated recovery.
- [x] Run `python -m unittest tests.test_vision_install -v`; observe missing 2B
  files/provenance and incomplete-recovery failures before implementation.
- [x] Ensure 2B on cache hits and new downloads; pin plans before download and
  reuse verified per-model manifests. Extract shared download checks if needed.
- [x] Rerun installer regression suites; confirm passing behavior.

## Task 3: docs, review and final verification

- [x] Update README/setup docs, document index and codemap (including inventory).
- [x] Run `python -m unittest discover -s tests -v`, all `tests/*.mjs` through
  `node --test`, and `git diff --check`. Record actual results below.
- [x] Review the whole diff against acceptance criteria, update product/design
  status and record remaining host/GPU/visual gaps.
- [x] Independent review found a retained-Hub-metadata recovery gap; add a
  cache-preserving download double and observe `Incomplete model` before fixing.
- [x] Force download for an existing file with a known wrong size and rerun the
  regression/full suites.

## Execution ledger

- Baseline: `python -m unittest tests.test_stages tests.test_vision tests.test_vision_install -q`
  passed 27 tests; `node --test tests/test_editor_semantics.mjs` passed 8 tests.
- Environment: sandboxed Python launcher could not access runtime metadata;
  approved unsandboxed environment probe confirmed Python 3.12.0 and NumPy 2.2.6.
- Task 1 red: `python -m unittest tests.test_stages tests.test_vision -q`
  ran 26 tests with 3 expected failures (missing option, no character proposals,
  missing load-failure feedback/history preservation for the unrecognized mode).
  `node --test tests/test_editor_semantics.mjs` ran 10 with 1 expected wrong-path
  failure (2B selection populated the 8B path).
- Task 1 green: same commands passed 26 Python and 10 Node tests. Qwen3-VL
  load/generate/chained failure cleanup characterization passed unchanged.
- Task 2 red: `python -m unittest tests.test_vision_install -v` ran 8 tests,
  with 3 failures and 2 errors caused by absent 2B support/files/provenance and
  no interrupted-download path. No environment errors counted as red evidence.
- Task 2 green: `python -m unittest tests.test_vision_install tests.test_cloud_install -q`
  passed 23 tests. A clean-install characterization was then added; the installer
  suite passed 9 tests, including the unchanged 9B new-workflow default.
- Shared download verification was extracted unchanged into `download_records`;
  the additive snapshot uses it while keeping larger-model cache identity intact.
- Full Node run: `$nodeTests = @(rg --files tests -g '*.mjs'); node --test $nodeTests`
  passed 42 tests. Full Python run initially hit the sandbox launcher restriction
  and was rerun with approved outside-sandbox access. Logs: ignored
  `outputs/qwen2b-python-tests.log`, `outputs/qwen2b-node-tests.log`.
- Final review: one independent read-only reviewer examined the whole diff.
  It found one Important recovery bug: Hub immutable-commit metadata can return
  an existing truncated file without checking size. No deferred minor findings.
- Final fix red: `python -m unittest tests.test_vision_install.VisionInstallTests.test_truncated_2b_file_with_retained_hub_metadata_is_redownloaded -v`
  failed with `Incomplete model: Qwen3-VL-2B-Instruct/model.safetensors`.
  Green: `python -m unittest tests.test_vision_install -q` passed all 10 after
  forcing a fetch for an existing file with a known wrong size. Complete cache
  hits still make no Hub calls. Context7 Hub research was added to the design.
- Final review ruling: installed ComfyUI conversion/save/reopen, actual model
  inference, GPU memory release/performance and visual point placement are
  unqualified because no host or real weights were exercised. These are explicit
  remaining acceptance checks; assuming they pass would overstate deployment readiness.
- Document check: `node outputs/check-qwen2b-docs.mjs` found no broken local
  links or unmapped maintained files across 113 files using codemap exclusions.
  The initial Python one-liner check failed from Windows shell quoting; the
  Node script performed the check successfully. No production TDD claim for docs.
- Workflow/dependency check: `git diff --quiet -- workflows/ltx-2.5-motion-track.official.json workflows/comfy-ltx-loop-motion.json pyproject.toml`
  passed; the official/adapted graph files and dependency pins remain unchanged.
- Final verification after the recovery fix: `python -m unittest discover -s tests -v`
  passed **107 tests** in 75.433s. All Node files via the command above passed
  **42 tests**. `git diff --check` passed (only Git's LF/CRLF conversion notices).
- Tasks 1–3 complete in the working tree. Product/design/setup/index/codemap and
  qualification notes reconciled. No commit, push, deployment or real-model run.
