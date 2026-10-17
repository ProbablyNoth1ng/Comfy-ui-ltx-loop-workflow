# Automatic RunPod installation

Use `runpod/comfyui:1.3.3-comfyuiv0.30.0-cuda13.0` with an NVIDIA Blackwell GPU.
The launcher fixture was extracted from image digest
`sha256:e8505fe1ba1b39cc6a140c2f01fe8d8d47f680cc7af45662ec0d77858fba8355`.
This installs the current BF16 workflow; its minimum GPU memory is not qualified.
The installer does not silently substitute quantized models.
The image is the base environment: its ComfyUI 0.30.0 cannot load the workflow's
LTX-2.5 diffusion video VAE. Before launch, the installer upgrades incompatible,
clean ComfyUI checkouts to v0.38.0 (commit
`6b747c0428c343e1417219641db93a4fb7cb69ae`). Existing compatible code is kept.

## Storage

Use the Pod's temporary container disk. No Network Volume is needed.

1. Set Container disk to 250 GB as a starting allocation for the image, copied
   ComfyUI environment, BF16 model files and outputs. Actual required space is
   checked before model downloads; large numbers of renders can need more.
2. Set Volume disk to 0 GB and do not attach a Network Volume. Leave the template
   mount-path field at `/workspace`; without a volume, this is simply a directory
   on the container disk, not a separately provisioned storage resource.
3. Expose HTTP 8188 for ComfyUI and 8888 for JupyterLab. TCP 22 is optional for SSH.

Every fresh Pod downloads the project, nodes, dependencies and models from their
existing GitHub/Hugging Face sources automatically. Container-disk files are lost
when the Pod stops or is deleted. Download finished videos, frames and saved
workflows before stopping it. The container disk itself is billed by RunPod;
this configuration avoids a separate persistent volume.

## Start command

Publish `cloud/install.py` and `cloud/runpod_entrypoint.py` in your repository
before using this command. Both files must be available on the selected revision.
Then generate the short command locally:

```powershell
python tools/build_runpod_command.py
```

The generated `outputs/runpod-start-command.json` is the **complete value** for
the template's Start command field. It explicitly overrides the image's Docker
entrypoint using RunPod's supported JSON `entrypoint`/`cmd` format. A plain CMD
does not replace the official image's `/start.sh` entrypoint.

The JSON contains only a small loader, below RunPod's 4000-character `dockerArgs`
limit. It clones the project and runs `cloud/runpod_entrypoint.py` from:

```text
https://github.com/ProbablyNoth1ng/loop-video.git
```

The installer preserves the official launcher: SSH, Jupyter, ComfyUI
initialization and its virtual environment still run. It inserts installation
immediately before the launch of ComfyUI, with `--cache-none` for the staged
workflow. If the image launcher changes incompatibly, startup fails explicitly
instead of launching a partially installed environment. The adapter recognizes
both the image's `COMFY_ARGS` array launch and the older `FIXED_ARGS` launch.
The extracted image launcher is covered by local regression tests.

## Environment variables

| Variable | Value |
| --- | --- |
| `COMFY_LTX_LOOP_REPO` | Optional repository URL; defaults to the URL above |
| `COMFY_LTX_LOOP_REVISION` | Optional Git branch/tag/commit, used on first clone |
| `LTX_REVISION` | Optional LTX Git branch/tag/commit, used on first clone |
| `COMFY_LTX_LOOP_VISION_MODEL` | Larger model: `Qwen/Qwen3.5-9B` for new installs, or `Qwen/Qwen3-VL-8B-Instruct`; existing installs retain their choice when unset. Qwen3-VL-2B-Instruct is installed alongside either choice. |
| `HF_TOKEN` | Hugging Face token with read access to the required models |
| `JUPYTER_PASSWORD` | Your JupyterLab token/password |
| `FILEBROWSER_PASSWORD` | Your FileBrowser password if exposing port 8080 |

Use RunPod Secrets for tokens. First accept any access conditions required by
the LTX-2.5 and Gemma repositories using your Hugging Face account. The installer
cannot accept account agreements for you. It does not print `HF_TOKEN` or put it
in the generated command. Your current public GitHub repository needs no token.

## What happens on boot

- Clone Comfy LTX Loop and ComfyUI-LTXVideo into `/workspace` on the container disk.
- Check for the LTX-2.5 diffusion VAE loader in ComfyUI and update incompatible
  core code to the pinned revision. Local changes block this update explicitly;
  models, user workflows and custom nodes are preserved.
- Install project, vision, ComfyUI and LTX requirements using ComfyUI's active
  virtual environment, while constraining Torch/torchvision/torchaudio to the
  image's installed versions. Install ffmpeg if missing.
- Connect the Comfy LTX Loop custom nodes.
- Download the six exact model files declared by the official Motion Track
  workflow, the selected larger Qwen snapshot and Qwen3-VL-2B-Instruct
  (each including configs/tokenizer/weights),
  and Real-ESRGAN's `realesr-animevideov3.pth`.
- Resolve Hugging Face models to immutable commits before downloads, check free
  disk space, file sizes and available source SHA256 hashes, and validate the
  Real-ESRGAN checkpoint with Spandrel.
- Add both workflows to ComfyUI's saved workflows, preserving existing copies.
- Start ComfyUI on 8188 only after installation succeeds.

The first boot includes large downloads and checksum reads. Its duration depends
on the network and disk throughput. During setup, use the Pod logs or Jupyter;
the ComfyUI port is not ready yet. Look for `COMFY_LTX_LOOP INSTALLED`, followed by
ComfyUI's normal server startup. Open `comfy-ltx-loop-motion` from saved workflows.
Successful installation is not proof of GPU rendering or visual loop quality.

When files still exist, another invocation uses the existing project/LTX revisions,
installed dependencies and model files. Only incompatible ComfyUI core code is
updated to the pinned compatibility revision; compatible code is not pulled.
An existing `/workspace/comfy-ltx-loop` checkout does not automatically pull a
published adapter fix on restart. Use a fresh Pod or update that checkout explicitly.
A new or cleared container disk always gets a complete installation. Fast model checks
compare recorded sizes, plus the small upscale model's checksum. They do not
rehash all large weights on every boot. Interrupted HF downloads reuse their
local download metadata on retry while those files remain on disk.
The vision selection participates in download-cache identity. Switching to
Qwen3.5 retains installed Qwen3-VL files for comparison. Download manifests
record immutable HF revisions and file checksums; no vision weights download
during Prepare.
Legacy manifests migrate with their existing pinned revisions. The additional
2B snapshot is installed even when the larger model is already cached; it has
its own `vision-Qwen3-VL-2B-Instruct-plan.json` and
`vision-Qwen3-VL-2B-Instruct.json`. Complete 2B files are reused when switching
the larger selection. Choose **local Qwen3-VL 2B** in the editor for any Prepare
action, then review its suggestions before rendering. Per-model ready
manifests and `vision-*.json` provenance live in `.comfy-ltx-loop-install/`, so
switching back to an installed snapshot reuses its recorded revision. Newly
copied workflows match the selected analyzer; saved workflows remain unchanged.
Missing/truncated models trigger recovery.
Checksums, model revisions and `pip freeze` are retained under
`ComfyUI/.comfy-ltx-loop-install/`. Run one Pod at a time against this installation.

## Video VAE loading error

If node `5004:5601` reports mismatched `decoder.conv_in.weight` shapes
`[2048, 128]` versus `[2048, 128, 3, 3]`, ComfyUI selected its generic Stable
Diffusion VAE loader for `ltx-2.5-video-vae-bf16.safetensors`. ComfyUI 0.30.0
lacks the required diffusion decoder branch. This is a core loader compatibility
problem, not a VRAM allocation failure. The compatible loader recognizes
`decoder.conv_in_x_t.weight` and constructs `CausalDiffusionVAE`.

Publish the updated `cloud/install.py`, then use a fresh Pod or update the
existing project checkout explicitly and rerun the installer before restarting
ComfyUI. A restart with an old project checkout will keep using its old installer.
Keep the video VAE selected in the workflow; the compatibility fix retains its
diffusion decoder and does not change the official workflow or model downloads.
ComfyUI core revisions are included in the dependency fingerprint so an upgrade
also refreshes requirements under the image's Torch version constraints.

Sources: [ComfyUI 0.30.0 VAE loader](https://github.com/Comfy-Org/ComfyUI/blob/v0.30.0/comfy/sd.py),
[ComfyUI 0.38.0 VAE loader](https://github.com/Comfy-Org/ComfyUI/blob/6b747c0428c343e1417219641db93a4fb7cb69ae/comfy/sd.py).

If setup fails, fix the issue shown in the logs and retry. Stopping the Pod clears
the temporary files; a new boot downloads them again. Account
access errors require fixing the token or accepting the model's terms. A failed
installation never writes a completed models marker.

## Manual installation

For an already initialized ComfyUI environment with the project available:

```bash
python3.12 /workspace/comfy-ltx-loop/cloud/install.py
```

This command selects the official ComfyUI virtual environment if invoked from
system Python. Stop/restart ComfyUI after manual installation so it loads the
new nodes. Use the generated Start command for automatic setup on future boots.

Sources: [RunPod template command format](https://docs.runpod.io/pods/templates/manage-templates),
[official image launcher](https://github.com/runpod-workers/comfyui-base/blob/main/start.sh),
[RunPod storage](https://docs.runpod.io/pods/storage/types).
