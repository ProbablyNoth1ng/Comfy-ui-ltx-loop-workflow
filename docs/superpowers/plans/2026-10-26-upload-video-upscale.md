# Upload video for Upscale Implementation Plan

> For agentic workers: use superpowers:executing-plans. Work inline and record
> checks here. No commit, push or deployment is authorized.

Goal: upload an entire personal video and finish it through the existing Upscale.
Architecture: streaming input inventory → reusable disk-backed import → existing
finish methods, with additive source widgets and unchanged graph connections.
Tech stack: existing Python/ComfyUI/aiohttp/FFmpeg and browser extension.
Spec: [design](../specs/2026-10-26-upload-video-upscale-design.md).

## Constraints and review focus

Preserve old workflows/CLI, rational timing, displayed orientation, no imported
near-16:9 crop, immutable originals, bounded image memory, no completed records on
failure/cancellation. Check inactive source validation, path containment, streamed
limits, upload cleanup and stale UI responses. No six-second truncation or loops.

## Task 1: Upload storage, probing and HTTP API

Files: videos.py, comfy_routes.py, test_videos.py, test_video_routes.py.
- [x] Write and run failing upload/probe/storage tests.
- [x] Implement unique storage, media validation, inventory and streaming endpoint.
- [x] Run targeted tests green and record evidence.

## Task 2: Import, compatible handles and finishing

Files: videos.py, candidates.py, staged_comfy.py, test_videos.py, test_stages.py.
- [x] Write/run failing real-media import/finish and node compatibility tests.
- [x] Implement disk normalization/cache, handle provenance, additive source inputs.
- [x] Verify fractional/VFR/rotation/long/short sources and original preservation.

## Task 3: Source selector, fixture and usage

Files: comfy_ltx_loop.js, test_previews.mjs, editor_harness.py, README.md.
- [x] Write/run failing source/upload/persistence/race/queue tests.
- [x] Implement source controls and normal imported-video playback.
- [x] Update fixture and usage; inspect served browser controls (native upload gap below).

## Verification and handoff

- [x] Python suite, Node suite, editor fixture and git diff --check (browser gap below).
- [x] Update product/design/plan/index/codemap and reconcile inventory/links.
- [x] Review full diff; separately record installed ComfyUI/GPU/visual gaps.

## Execution ledger

- Read product/spec index/qualification and owning modules before changes. Clean
  initial tree; created branch `feat/upload-video-upscale` in the supplied workspace.
- Context7 resolve/query completed for ComfyUI, FFmpeg and aiohttp; see design.
- Python launcher inside sandbox could not discover the installed runtime; approved
  execution outside sandbox found Python 3.12 with NumPy/Pillow. aiohttp test-only
  installation requested into ignored local `.test-deps`; no project dependency change.
- Baseline: `python -m unittest discover -s tests -v` → 115 passed;
  Node project suite → 45 passed.
- RED: `python -m unittest discover -s tests -p test_videos.py -v` → 9 tests
  failed on missing uploaded-video API and optional source widgets. GREEN after
  implementation → 9 passed, including independent CFR pixel-order comparison.
- RED: `$env:PYTHONPATH = '.test-deps'; python -m unittest discover -s tests -p
  test_video_routes.py -v` → missing GET/POST routes (404), cleanup assertion failed.
  GREEN → 4 passed against a real aiohttp test server, including chunked bodies.
- RED: `node --test tests/test_previews.mjs` → 4 new behavior failures (missing
  source callbacks/file control, one-path preview unsupported). GREEN → 11 passed.
  Native source widgets then hidden behind labelled DOM controls: assertion red/green.
- Ruling: an oversized multi-file request may return 413 before the one-file 400
  error, because the configured server limit applies to the whole request. Adjusted
  fixture sizes to test those failures independently; no production limit weakened.
- Ruling: use decoded-frame timestamps for video duration; a real FFmpeg VFR fixture
  reports container/stream duration 1.5 s but has visible frames ending at 1.9 s.
  Trusting the shorter metadata would truncate content. The disk timestamp scan costs
  another FFprobe pass; it avoids holding per-frame metadata in RAM.
- Independent whole-change review completed. Important fixes: POSIX ENOTEMPTY
  cache race, unknown SAR fallback, and cancellation during final frame hashing.
  Tests reproduced two errors and one missing-cancellation assertion before fixes;
  targeted `test_videos.py` → 13 passed after fixes. Every supported container and
  unspecified SAR have real fixtures. VFR now also checks monotonic source-frame
  content order, first/last content and repeated frames.
- Additional UI regression: late candidate inventory could undo the latest Render
  in uploaded mode. Test failed with old/new candidate mismatch, then passed after
  adding independent candidate-list invalidation. Preview suite → 12 passed.
- Final review: minor (deferred): content-addressed cache provenance retains the
  first upload's filename/ID for identical bytes. Widgets retain the selected ID;
  content hash remains accurate. No extra source copy or generation metadata added.
- Browser fixture: `python tests/editor_harness.py` served root, extension/scripts,
  inventories, record and MP4 endpoints. Chrome DOM showed source selectors and
  upload/refresh controls. Native file chooser automation failed; extension file-URL
  permission is required. Later browser reconnection timed out. Do not count this
  as a completed browser upload or installed ComfyUI qualification.
- Final Node project suite: 50 passed, 0 failed/skipped (after review fixes).
- Final Python project suite: `$env:PYTHONPATH = '.test-deps'; python -m unittest
  discover -s tests -v` → 132 passed in 140.053 s, 0 failed/skipped. This includes
  all actual HTTP tests and real FFmpeg fixtures. Full log is in ignored local
  `outputs/python-suite-final.log`; Node log is `outputs/node-suite-final.log`.
- Document/inventory verification: `node outputs/verify-docs.mjs` → 125 maintained
  files, no unmapped/stale files, no broken links in changed documents.
  `git diff --check` → passed. Product/design/plan/index/codemap/README reconciled.
- Handoff: implementation complete locally. No commit, push, deployment, dependency
  upgrade or official LTX workflow change. Installed ComfyUI conversion, native
  browser upload completion and GPU/visual acceptance remain pending; local test
  evidence is not a substitute for those checks.
