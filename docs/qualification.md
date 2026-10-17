# GPU and visual qualification

Status: **pending**. No provider instance was available. Local CPU tests do not
prove LTX inference, Qwen anime landmark accuracy, Spandrel weight compatibility
or ComfyUI browser behavior on a provider.

## 2026-10-17 lightweight Qwen point proposals

Local regression tests exercise the 2B selection for character, background and
combined preparation, review invalidation, saved/custom paths, additive model
installation, independent pinned manifests, cache reuse and interrupted/missing
snapshot recovery. Hub and model inference boundaries use doubles. No 2B weights
were downloaded or run here. The final full suites passed 107 Python and 42 Node
tests, and document/inventory/diff checks passed. On a configured host, verify all three Prepare
actions, real point placement against the source, manual correction and renewed
review, model unload before Render, actual GPU memory use and installed ComfyUI
save/reopen and conversion. Compare 2B with the installation's larger model using
the same source/instructions; capture both per-model manifests and stage evidence.
The official LTX baseline remains unchanged and still requires qualification.

## 2026-10-16 optional points implementation

Local tests cover direct Render with `[]`, no Qwen call, text guidance, selective
track groups, review invalidation and candidate metadata. The editor fixture is
a simulated queue. The installed ComfyUI-LTXVideo revision, its empty-track guide
frame, downstream inference, GPU memory use and resulting anime motion have not
been run or visually accepted here. On deployment, capture the exported Render
API graph and stage history for character-only, background-only, both and no-point
runs; verify the saved candidate records `review.state=not_required` only for
the no-point run, then inspect motion, camera stability and loop seam.

## 2026-10-08 faster finishing implementation

The source now offers Fast (FFmpeg Lanczos), Balanced AI (installed anime weights
in supported FP16 with adaptive tiles), and Original AI (legacy path). The new
editable workflow defaults to Fast/1080p; old Upscale nodes keep Original AI/1440p.
Local Node tests passed (37); an FFmpeg 9.0 command probe cropped two 1290x720
frames and wrote 1920x1080 PNGs in order. Its silent MP4 had one video stream,
two frames at 8 FPS and 1920x1080. The local Python suite could not run: Windows PyManager
reports no installed Python and network restrictions prevented `uv` from
installing one. There is no saved LTX candidate or local GPU in this checkout.
Required follow-up on a configured host: run the Python suite, then time all
three methods against the same six-second 1280x720 LTX candidate, check Fast
against the under-25%-of-Original target, and inspect faces, linework, flicker
and seam side by side. Record elapsed times and visual judgment separately.

## 2026-10-06 background animation implementation

The local Python and Node suites cover grouped validation, independent manual and
model preparation, failure preservation, stale preparation settings, track
exclusion, prompt guidance, widget order, and Prepare-stage isolation. The local
browser harness showed the two lists, background controls, successful review,
separate Run preparation choices, and toggle-off hiding. Its queue is simulated.
The prior RunPod pod was terminated and this workspace has no configured live
ComfyUI endpoint. Deployed `graphToPrompt()` conversion and a representative
foliage render remain pending, including camera stability and seam inspection.

## Official generation baseline

Import `workflows/ltx-2.5-motion-track.official.json` unchanged. Install its exact
models and run its defaults on the selected GPU. Do not alter sampler, precision,
LoRA, resizing or decoding for this first run. Save its exported API graph,
ComfyUI logs and output. Export the API graph using ComfyUI's developer option
after selecting the source image. The observer queues that graph without edits:

```bash
python /workspace/comfy-ltx-loop/tools/qualify_ltx.py \
  --comfy "$COMFY_ROOT" --api-graph baseline.api.json \
  --image-digest 'REGISTRY/IMAGE@sha256:ACTUAL_DIGEST' \
  --record /workspace/comfy-ltx-loop/evidence/cloud-baseline.json
```

It records queue/history result, wall time including queue wait, sampled total
GPU memory (not isolated process allocation), package freeze, ComfyUI/LTX
revisions and installed model/workflow hashes. Preserve output history and
actual dimensions/frame count. The unchanged baseline defaults differ from
the adapted six-second recipe; run and record the adapted recipe separately.
Reconcile lost queue responses/timeouts against queue/history; never blindly
resubmit an expensive job.

Qualify a supported minimum only after repeated successful actual runs of
Prepare → vision unload → Render → decode/save → Upscale. Record peak memory,
stage runtimes, storage, image digest, CUDA/driver and exact dependency/model
revisions. Check Qwen tensors are not resident during generation. Save a tested
lock from those results; weight file size alone cannot qualify a GPU.

## Browser checks

For the Motion Track IC-LoRA guide, confirm a 1312×736 input at the default
720 short side prepares a 1344×768 reviewed canvas and a 672×384 half-resolution
guide. After updating the project on RunPod, restart ComfyUI, use **Prepare
points**, inspect the paths, and click **Accept point review** again. Render and
confirm node `9002:5012` completes and decoded frames are 1344×768. Record the
node history and output dimensions here before marking GPU validation complete.
Previously saved rendered candidates can still be selected for finishing.

Test portrait/landscape sources, corner points/padding edges, point/path editing,
workflow save/reopen, and trajectory alignment in tracks_preview. Test missing
vision weights, malformed JSON, missing landmarks and out-of-bounds paths:
feedback must leave manual correction available. Review must stale on image,
prompt, timing, canvas and point changes. Test switching candidates and a full
ComfyUI restart. Inspect `/prompt` requests: Prepare contains no generation;
Render contains no Upscale; Upscale contains no generation.

Verify the current frontend's flattened subgraph API export. The adapted Input
Parameters no longer connects its image input directly to its `resized` output.
The already transformed editor canvas feeds the top-level Preprocess image input
without another resize. Capture `graphToPrompt()` output on the deployed frontend
before claiming this conversion is qualified.

## 2026-10-04 local staged-point implementation evidence

- `node --test tests/test_stages.mjs tests/test_motion_workflow.mjs tests/test_editor_geometry.mjs`: 14 passed, including portrait/landscape image and CSS letterbox coordinate mapping.
- `python -m unittest tests.test_stages -v`: 4 passed.
- `python -m unittest discover -s tests -v`: 41 passed.
- Local browser fixture at `127.0.0.1:8766`: manual Prepare displayed an empty
  plan and Add point created a numbered row with normalized coordinates. A Qwen
  sample event displayed four labeled rows; selecting the first row populated
  its label and path controls. Disabling that point changed its row, and the
  state survived simulated reopen. A Qwen failure event showed explicit
  feedback, an empty list, and disabled review. An invalid Prepare event after
  a reviewed plan cleared the old plan and blocked Render. This fixture
  simulates queueing and does not run
  ComfyUI's `graphToPrompt()`.
- The pod was terminated, so deployed checks were deferred at the user's
  request. The workflow conversion, `/prompt` payloads, 2752 × 1536 image run,
  73-frame render, Qwen model inference, save/reopen in ComfyUI, and GPU preview
  remain unverified. The frontend now logs stage, target ID, selected node
  IDs/classes and error stack without logging image bytes or prompt text, for
  that run.

## 2026-10-05 global Run interception evidence

- `node --test tests/test_queue_control.mjs tests/test_stages.mjs
  tests/test_motion_workflow.mjs tests/test_editor_geometry.mjs`: 23 passed.
  The checks cover cancellation before conversion, unchanged ordinary and
  partial queues, one auto-queue notice per graph, isolated-stage guards, and
  trailing API queue arguments.
- The local fixture served the updated main Run controls and
  `queue_control.mjs` over HTTP. It remains a simulated queue fixture and has
  not qualified dialog focus, keyboard Escape, or the installed ComfyUI
  frontend's `app.queuePrompt` signature.
- No installed ComfyUI frontend was present in this checkout or user profile.
  Deployed verification still needs to confirm main Run and the keyboard queue
  entry point, the current third-argument form, no `/prompt` request before a
  stage is chosen, and normal-workflow queueing.

## Real anime pilot

Use licensed portrait/landscape anime with closeups, fine hair, occlusion,
cel shading and detailed backgrounds. Record provenance and held-out examples.
Inspect face identity, hair tips, fixed roots/head/shoulders, camera/background
drift and seams over three continuous cycles. Endpoint mean error is evidence,
not perceptual acceptance. Retry visibly poor seams; never substitute ping-pong.

Review 1080p, 1440p and 4K finishes for line preservation and temporal flicker. Verify
144 playback frames, 24 FPS, six-second silent MP4 and distinct candidate/finish
names. Retain all 145 raw generated frames and sidecar records.

## 2026-10-05 semantic-point upgrade and artifact investigation

The user confirmed the A40 pod was terminated. This checkout contains older CPU
demo outputs, but no affected LTX `candidate-*/record.json`, raw PNG sequence or
track-guide export. The first affected frame and artifact cause cannot be
identified from the available evidence. No model-accuracy or animation-quality
improvement is claimed.

Local tests cover role-driven paths, stationary anchors, semantic review
invalidation, partial JSON responses, coordinates and missing snapshots. Model
boundary doubles exercise both published snapshot configurations, thinking
disablement and object release on success, loading failure, generation failure
and chained exceptions. This proves reference cleanup behavior, not actual GPU
VRAM recovery. The real browser fixture exercises 20 synthetic semantic points;
synthetic coordinates do not qualify anime grounding.

Final local verification: `python -m unittest discover -s tests` passed 67 tests;
all six JavaScript test files passed 32 tests; `git diff --check` passed. Browser
QA confirmed distinct point colors, anchor controls, role/disabled state after
reopen, and persisted role-reason text after the oninput fix. Fresh-context code
review found no remaining Critical or Important issues after the installer and
chained-exception fixes.

Before accepting Qwen3.5 as an upgrade, run both analyzers on the same source,
prompt and requested parts. Save proposals, feedback, source hash and the
installer's per-model `vision-*.json` manifests with immutable revisions and
checksums. Inspect distinct hair tips, intermediate points, roots and visible
face/body anchors against the original image. Hidden features must be omitted;
stationary and unrequested motion must be anchors. Compare placement and prompt
compliance independently of point count.

On the next GPU deployment, use these controlled comparisons:

1. Retain the affected original candidate and its exact reviewed plan, seed,
   timing, render settings and source. Compare the source with each `raw/` PNG,
   corresponding exported `frames/` PNG and the Motion Track guide. Locate the
   first affected frame by visual inspection, then record its index, file hashes,
   crops and whether the artifact is already present in the raw decode. Align
   raw canvas crops using `motion_plan.transform.content`; the final raw endpoint
   has no playback-frame counterpart.
2. Copy the original plan and add only visible stationary face anchors. Keep
   every existing moving path and render setting unchanged; accept a fresh
   review and render a separate candidate.
3. Retain those anchors and add intermediate points along visible moving hair
   strands. Preserve the original moving paths and render settings, accept review
   again and render another candidate.
4. Compare hair/eyebrow layer order, face identity, motion and the forward loop
   seam across the original and both variants. Record observed changes separately
   from the hypothesis that reconstruction of overlapping hair/eye linework
   causes the artifact. Positional tracks do not explicitly encode layer order;
   this hypothesis remains unverified. See [LTX motion-control guidance](https://docs.ltx.io/open-source-model/feature-guides/structural-control/motion-control).
5. Qualify Prepare → edit/review → Render → 1080p upscale on the GPU. Record
   stage histories and runtimes, actual VRAM after analysis, raw/exported
   dimensions and silent video FPS/frame count. Verify finishing consumes only
   the saved candidate and retains its original PNGs and timing. Repeat landscape
   and portrait finishing at all three resolutions; keep 1440p as the default.

The renderer remains the official LTX path. Strict masks and source compositing
are outside this change. [Qwen3.5 model card](https://huggingface.co/Qwen/Qwen3.5-9B)
and [Transformers 5.2 implementation](https://github.com/huggingface/transformers/blob/v5.2.0/src/transformers/models/qwen3_5/modeling_qwen3_5.py)
support the loading interface; GPU inference and visual acceptance remain pending.
