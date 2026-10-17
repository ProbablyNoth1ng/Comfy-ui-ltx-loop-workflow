# Strict motion areas design

Date: 2026-10-17. Status: implementing; installed renderer, GPU and visual qualification pending.
Product requirements: [P-16 and P-17](../../product-spec.md), preserving P-01, P-05, P-07 and P-08.

## Intent and scope

Free motion remains the compatible default. `only_pointed_parts` makes approved source-coordinate masks the sole editable pixels: enabled moving points in enabled groups authorize their own areas; anchors and disabled points authorize none. It includes trajectory travel in the area and restores a fixed source reference outside the union on every candidate and finished PNG.

## Contracts

`motion.py` owns plan normalization, stable point IDs, area validation, active moving authorization, fingerprints and strict review. Masks are one-channel source-size PNG-equivalent arrays encoded as nested rows in the plan for portability. `candidates.py` owns exact compositing and persists source/mask artifacts. `staged_comfy.py` passes source pixels into saving and rejects strict rendering without accepted areas. The editor changes point buttons and invalidates review when it edits strict state.

Segmentation is preparation-only. SAM 2.1 Small is called behind a local adapter with Qwen point prompts; failure preserves editable data and does not mark strict review current. The model/predictor are released in success and failure paths. The adapted workflow must contain its mask adapter before strict inference; this source change can validate the graph contract but cannot qualify installed ComfyUI conversion.

## Compatibility and research

Older plans omit `render_mode` and default to `free_motion`; missing point IDs are deterministically assigned on normalization. Context7 lookup 2026-10-17: `/facebookresearch/edgetam`, official high-reputation documentation. `SAM2ImagePredictor` uses `set_image` then `predict(point_coords, point_labels, multimask_output=True)` and selects the highest-IoU mask. The local adapter uses that shape, but does not alter Torch or existing dependency pins. Actual SAM 2.1 Small package/weight revision and hash must be recorded on deployment.

## Acceptance and tests

`test_motion.py`: legacy free default, invalid/stale strict review, authorization, identifiers and areas. `test_candidates.py`: synthetic protected-pixel equality through candidate save and every finish method. `test_stages.py`: strict empty-point rejection and source persistence. `test_editor_semantics.mjs`: two add buttons and strict review invalidation. Local tests cannot prove graph conversion, latent masking, model unload on a GPU, segmentation quality or visual loop quality.

## Delivery boundary

The plan is [here](../plans/2026-10-17-strict-motion-areas.md). Record red/green and final suite results there. Deployment must verify the installed graph’s mask adapter, actual source-backed latent masking, Qwen/SAM release, reviewed-part motion, frozen cars and loop closure.
