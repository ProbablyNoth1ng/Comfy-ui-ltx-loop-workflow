# Installation and storage

Perform installation before creative work. Neither provider has a tested
GPU minimum yet. Use an authenticated provider gateway for ComfyUI.

## RunPod

For automatic node/dependency/model installation on Pod creation, see
[RunPod automatic installation](runpod-autoinstall.md). The steps below are
the older manual path; `cloud/bootstrap.sh` alone does not download models.

Use a ComfyUI template with enough container disk space for the install, models
and outputs. A Network Volume is optional. Without one, set Volume disk to 0 GB;
`/workspace` is an ordinary directory on the temporary container disk. A common
template path is `/workspace/runpod-slim/ComfyUI`; use your actual template path.
Download outputs before stopping/deleting the Pod; a cleared disk requires
installing and downloading the models again. The automatic launcher does this
on each fresh Pod.

```bash
export COMFY_ROOT=/workspace/runpod-slim/ComfyUI
export PROJECT_ROOT=/workspace/comfy-ltx-loop
bash "$PROJECT_ROOT/cloud/bootstrap.sh"
bash "$PROJECT_ROOT/cloud/start.sh"
```

Place this project at PROJECT_ROOT first. Install ffmpeg/ffprobe using your
image's package manager if absent. Expose 8188 through the provider gateway.
The legacy `runpod/start.sh` checks the older CLI environment lock; use the
cloud launcher for this workflow.

## Vast.ai

Use a ComfyUI image or install ComfyUI in its CUDA Python environment. Put both
ComfyUI and this project on the provider's actual persistent mount:

```bash
export COMFY_ROOT=/workspace/ComfyUI
export PROJECT_ROOT=/workspace/comfy-ltx-loop
bash "$PROJECT_ROOT/cloud/bootstrap.sh"
bash "$PROJECT_ROOT/cloud/start.sh"
```

`/workspace` is an example; mounts vary by offering/image. Expose 8188 through
the authenticated connection. Verify which storage survives stop, replacement
and destroy operations. Copy models, workflows and outputs to retained storage
before destroying an instance; instance disks are not assumed to survive.

## Models and dependencies

Bootstrap installs Comfy LTX Loop's vision extra and ComfyUI-LTXVideo. It does
not download gated weights or replace the template Torch/CUDA installation.
Dependency ranges are installation candidates, not a tested lock. Record the
installed revisions/package freeze during qualification.

Install the models in the official workflow's Model Links note into its named
ComfyUI directories. Accept Hugging Face access terms first using your account.
Keep the same BF16 distilled transformer, Gemma 4 encoder/enhancer, video/audio
VAEs and Motion Track IC-LoRA files for baseline and adapted validation.

Automatic installation downloads Qwen3-VL-2B-Instruct into
`$COMFY_ROOT/models/Qwen3-VL-2B-Instruct` alongside the selected larger model.
New installations default to Qwen3.5-9B in `$COMFY_ROOT/models/Qwen3.5-9B`.
Qwen3-VL-8B-Instruct remains supported in
`$COMFY_ROOT/models/Qwen3-VL-8B-Instruct`; existing installations retain their
larger-model selection. All require configs, tokenizer and weights, plus
`transformers>=5.2,<6`. Set `COMFY_LTX_LOOP_VISION_MODEL=Qwen/Qwen3-VL-8B-Instruct`
or pass `cloud/install.py --vision-model Qwen/Qwen3-VL-8B-Instruct` to select it.
Choose **local Qwen3-VL 2B** in the editor to use the smaller model for Prepare
character, background or both. It keeps the same point rules and review step;
its memory use and placement quality still need host qualification.
Each snapshot has its own immutable revision and SHA256 manifest under
`$COMFY_ROOT/.comfy-ltx-loop-install/`. Setup reuses complete snapshots and
recovers interrupted/missing files from their pinned plans on retry.
Set the editor's `vision_model`
to that absolute path or use the populated relative path. Switching preparation
updates bundled model paths; custom paths and saved widget positions are retained.
Changed models require preparing affected groups and accepting review again.
The loader dispatches from the local snapshot's configuration and disables
Qwen3.5 thinking for structured JSON. Prepare uses `local_files_only=True`; it never calls a
hosted service or downloads weights during creative work. Missing weights give
editor feedback and leave manual placement available. Anime landmarks require
visual validation against the original source image.

Install [realesr-animevideov3.pth](https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-animevideov3.pth)
in `$COMFY_ROOT/models/upscale_models/`. Finishing uses ComfyUI's Spandrel support
and tiled Torch inference; the older BasicSR package is not needed. Finishing
records include the actual upscale weight hash.

## Retained data

If persistence is desired, keep `models/`, `input/`, `output/`, user workflows
and the project on retained storage. For container-disk-only RunPod sessions,
download the needed artifacts before stopping the Pod. Each unique candidate
directory retains `raw/` (145 generated frames),
`frames/` (144 playback frames), `record.json`, `loop.mp4` and `seam.mp4`.
Each finish retains its own enhanced PNGs, record and previews. Frame hashes are
verified before finishing; do not rename/remove frame files.

After restart, reopen the saved workflow. Completed candidates load newest first;
the saved selection is restored, or the newest render is selected. Changing the
candidate dropdown automatically plays its previews. Each completed render
becomes the selected candidate for upscale. Finishing has no dependency on source image/editor/video
models. Initial generation still materializes the official decoded batch;
RENDER_HANDLE and finishing never retain that full tensor batch.
