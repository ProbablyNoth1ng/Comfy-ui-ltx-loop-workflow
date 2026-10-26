# Comfy LTX Loop · ComfyUI anime loops

Project context: [product specification](docs/product-spec.md),
[code map](codemap.md), [technical specs and plans](docs/superpowers/README.md),
and [agent workflow rules](AGENTS.md). Every implementation updates the paired
specs, checks current library docs with Context7, and uses tests before production code.

Load image → enter character motion → **Prepare character points** → review/edit → **Render**
→ preview → optionally **Upscale** → save. Creative work stays inside ComfyUI.
The existing CLI remains compatible: see [legacy CLI](docs/legacy-cli.md).
The new animation path does not require producing or accepting Workflow A.

Import [comfy-ltx-loop-motion.json](workflows/comfy-ltx-loop-motion.json) after
[cloud installation](docs/cloud-setup.md).

RunPod can install all nodes, dependencies and model weights at first boot:
see [automatic installation](docs/runpod-autoinstall.md).

1. Load one anime image. Set the motion prompt and requested parts (`auto` by
   default, or a comma-separated list) in **Prepare and review**. Choose
   **local Qwen3.5** (default), **local Qwen** (Qwen3-VL 8B),
   **local Qwen3-VL 2B**, or **manual** preparation. Automatic setup installs
   2B alongside the selected larger model; changing models requires preparing
   affected points and accepting review again.
2. Click **Prepare character points**. Local Qwen proposes normalized character landmarks and
   unloads before generation. Failed analysis leaves the editor available with
   feedback; add points manually or retry.
   Analysis aims for 16–24 useful visible points, adapting to the image; hidden
   anatomy is omitted. Valid partial suggestions survive with omission feedback.
3. Enter **Background motion** when selected scenery should animate. This always-visible
   editor field enables background animation when it contains non-whitespace text;
   clearing it disables tracks while retaining saved background points. Choose **Model**
   (default) or **Manual**, then click **Prepare background points** or
   **Prepare character + background points**. The instruction is required before
   background or combined preparation. Model uses the same Qwen snapshot;
   Manual keeps editable points without loading it. Each preparation updates only
   its group. Failed model analysis preserves existing points and reports feedback.
4. Use **Visible points** to show Character, Background, or All on the shared source
   image. Hidden points cannot be selected or dragged. Use **New point group** before
   placement; it affects only new points. Empty groups explain how to add points.
   Character points are circles; background points are squares.
   Green points move; blue points anchor stationary parts; disabled points are gray.
   A row and its dot select the same point; disabled points appear muted. A
   manual or failed-Qwen Prepare shows an empty list with an Add point prompt.
   Move, add, delete or disable landmarks. Select a point and drag path handles;
   edit its label, Part / object, role, reason and strength. Select the active group
   before placing new points. Scrub or play trajectories.
   New proposals use semantic roles: only motion requested by the prompt moves.
   Changing a role resets the path to stationary or gently returning motion.
   Legacy points retain their existing paths. Enabled background animation needs at
   least one enabled moving background point. Click **Accept point review** before rendering.
5. Click **Render** for the official LTX-2.5 single-stage Motion Track pipeline.
   Continuous and forward seam previews play automatically in **Render preview**. Change
   seed for another candidate. Changing the source image clears both groups.
   Changing motion instructions or preparation settings requires preparing the
   affected group again. Timing and canvas changes preserve normalized paths but
   require renewed review. Clearing Background motion excludes its tracks while
   retaining saved points. Stationary anchors guide
   unselected areas, though generation may drift.
6. The last completed render is automatically selected in **Select saved candidate**.
   Choose another original render in its dropdown to preview it automatically.
   Optionally choose a finishing method and click **Upscale**. New workflows default
   to **Fast** at 1080p: FFmpeg Lanczos resizing without AI detail. **Balanced AI**
   uses the installed anime model in FP16 when supported, with adaptive tiles.
   **Original AI** uses the existing model path. Existing saved workflows keep
   their Original AI node and 1440p default. Re-select the same candidate and
   run another method to compare separate finishes.
   Resolutions use short sides of 1080/1440/2160, preserving orientation and
   aspect ratio with even dimensions. Finishing reads saved PNGs and
   keeps the same frame count, FPS and timing. Review linework, faces, flicker and
   the seam, then click
   **Save silent MP4**. Lossless frames remain beside the output.

To upscale your own video, use the same **Select saved candidate** node: choose
**Uploaded video** under **Upscale source**, click **Upload video**, and choose
one MP4, MOV, MKV, WebM or AVI from your computer. Previously uploaded videos are
listed by filename; **Refresh videos** reloads them. The source details show
displayed dimensions, duration and exact output FPS. Choose Fast, Balanced AI or
Original AI and 1080p, 1440p or 4K, then click **Upscale** (or Run → Upscale).
Prepare and Render are not needed. The whole clip is processed, including videos
longer than six seconds, with normal playback rather than a loop or seam preview.
Download the separate **silent MP4**; PNG frames remain beside it.

Uploads retain their original bytes under `ComfyUI/input/comfy-ltx-loop-videos/`;
imports and results live under `ComfyUI/output/comfy-ltx-loop/`. ComfyUI's configured
upload limit applies. Invalid or undecodable videos are rejected. Orientation and
aspect ratio are preserved, including rotation metadata; the near-16:9 crop used
for generated renders does not apply. VFR is normalized to the positive average
frame rate (falling back to the nominal rate): frames may repeat/drop, with
duration preserved within one output frame. Fractional FPS stays fractional.
The selected mode/video is saved in the workflow. A later Render updates the saved
render choice without switching away from your video. Choose **Saved render** to
return to generated candidates; older workflows start in that mode.

Use **Run** to choose exactly one animation stage: **Prepare character points**,
**Prepare background points**, **Prepare character + background points**, **Render**, or **Upscale**. The chooser submits one stage and does not apply
Run's batch count. The node stage buttons remain available. Preparing points
cannot queue generation; Upscale has only the saved-candidate branch upstream.
Save the workflow after editing: plans live in its serialized editor widget and
metadata. Reopening retains accepted points, including legacy character-only plans.
Render records live in `ComfyUI/output/comfy-ltx-loop/`. Saved candidates
load automatically after reopening; **Refresh candidates** reloads the list.

Defaults: six seconds, 24 FPS, seed 42, generation short side near 720 pixels,
original aspect ratio, stationary camera intent. Canvases use recorded edge
padding to multiples of 64, keeping the half-resolution Motion Track IC-LoRA
guide aligned to multiples of 32; exports remove that padding. Generation produces
145 frames, measures endpoint closure and exports 144 playback frames.
Returning tracks do not guarantee a seamless loop. Inspect face identity,
hair motion, background drift and seams; retry poor candidates. No automatic
ping-pong playback is used.

After updating from a version that used 32-pixel canvas alignment, run
**Prepare character points**, check the landmarks and trajectories, then click **Accept
point review** before **Render**. Plans with obsolete canvas transforms still
need fresh preparation. Saved rendered candidates remain available through
**Select saved candidate**.

The [unchanged official workflow](workflows/ltx-2.5-motion-track.official.json)
is retained for qualification. The adapted graph replaces input preparation
and output persistence while retaining model loading, the single-stage sampler,
IC-LoRA conditioning and tiled decoding. Prompt enhancement is off. The official
pipeline still uses audio latents; the adapted workflow exports silent videos.

**Qualification is pending:** local tests cover motion transforms, review
invalidation, stage isolation, candidate reopening and frame-preserving
finishing. The local editor fixture exercises manual and Qwen sample landmarks.
Deployed ComfyUI conversion, cloud GPU rendering and the real anime pilot still
need verification. No supported GPU minimum or measured inference runtime is
claimed. See [qualification](docs/qualification.md).

```bash
python -m unittest discover -s tests -v
node --test tests/*.mjs
```

Sources: [LTX Motion Control](https://docs.ltx.io/open-source-model/feature-guides/structural-control/motion-control),
[Motion Track IC-LoRA model card](https://huggingface.co/Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control),
[Qwen3-VL](https://huggingface.co/Qwen/Qwen3-VL-8B-Instruct),
[Qwen3.5-9B](https://huggingface.co/Qwen/Qwen3.5-9B),
[Qwen3-VL-2B-Instruct](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct),
[Real-ESRGAN anime model](https://github.com/xinntao/Real-ESRGAN/blob/master/docs/anime_video_model.md).
