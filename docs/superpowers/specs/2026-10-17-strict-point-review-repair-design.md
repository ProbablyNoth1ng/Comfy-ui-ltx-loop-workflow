# Strict point review repair design

Date: 2026-10-17. Status: implementing. Product requirements: P-04, P-05, P-16, P-17 in [the product spec](../../product-spec.md).

## Intent and scope

Repair the strict point journey so a prepared plan can propose areas, allow source-coordinate correction, pass authoritative review, and render. Keep existing points, groups, paths, IDs and Free motion compatibility. This change does not add the separate latent-mask renderer adapter or claim GPU/visual qualification.

## Behavior and acceptance criteria

The editor materializes filtered point entries before inspecting counts, preserving source index numbering. It reports preparation, area-needed, ready, accepted and processing states. A strict plan requires each active moving point to have a nonempty current area; diagnostics name the affected point numbers and labels. Render retains that diagnostic and writes a render-mode change into the plan before invalidating review.

SAM areas are generated only in Prepare or a new `areas` stage. The SAM 2.1 Small adapter uses each point as a foreground prompt, chooses the highest scored valid mask, adds its scaled trajectory coverage within source bounds, and releases model/image state on all exits. Existing current and manual areas remain. Results are discarded if the source, point geometry, workflow fingerprint or area request no longer match.

Manual paint/erase operate only on the selected moving point mask. The editor converts each stroke with the existing normalized letterbox mapping. Area metadata stores the source and point geometry fingerprint; moving geometry invalidates only that point's area, while labels invalidate only review.

## Architecture and contracts

`comfy_ltx_loop/areas.py` is the focused SAM/mask helper: geometry fingerprints, mask validation, trajectory coverage and adapter cleanup. `motion.py` owns active-point authorization and human diagnostics. `staged_comfy.py` invokes the adapter in preparation-only paths. `stages.mjs` and `queue_control.mjs` admit the isolated area stage, which keeps only Load Image and the motion editor. `comfy_ltx_loop.js` owns status and canvas editing.

## Library research

Lookup 2026-10-17 via Context7: `/facebookresearch/sam2`, official source, high reputation. The official image predictor is constructed from `build_sam2`, receives `set_image`, and `predict(point_coords, point_labels, multimask_output=True)` returns candidate masks plus scores; a single ambiguous point selects the maximum score. The installer pins an immutable SAM repository revision and checkpoint SHA-256 manifest, applies existing Torch constraints, and installs no optional CUDA extension. Source: https://github.com/facebookresearch/sam2.

## Test strategy

Python regression tests cover missing/stale diagnostics, SAM prompts, best-mask choice, travel coverage, failure cleanup and stage isolation. Node tests cover list counts, areas-stage pruning/guards, canvas paint/erase and strict review to render. Automated tests do not establish deployed ComfyUI conversion, GPU release, segmentation quality or visual quality.

## Delivery and evidence

Plan: [strict point review repair](../plans/2026-10-17-strict-point-review-repair.md). RunPod verification remains conditional on SSH access and is recorded separately from local tests.
