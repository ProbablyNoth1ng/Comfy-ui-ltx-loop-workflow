# Upload video for Upscale

## Intent and acceptance

[P-18, P-06, P-09 and P-12](../../product-spec.md#user-journey-and-requirements)
add a personal video source to the existing Upscale journey. Select Saved render
or Uploaded video in the existing source node, upload
one MP4/MOV/MKV/WebM/AVI, choose an existing method/resolution, preview and save
a separate silent MP4. Process the whole clip, without a six-second limit or loop
conversion. Keep original files, displayed orientation and aspect ratio. Imported
videos never receive the generated candidate's near-16:9 crop.

The owner's supplied plan approves this design and inline implementation.
No dependency/model updates, baseline workflow changes, commit, push or deployment.

## Architecture and contracts

- `videos.py`: streaming single-file multipart ingestion into the separate ComfyUI
  input `comfy-ltx-loop-videos` directory; opaque unique IDs, metadata, SHA-256,
  FFprobe validation and disk PNG import. No client-controlled filesystem paths.
  Only complete uploads appear in GET `/comfy-ltx-loop/videos`; POST returns one
  metadata object. Enforce the server's request body limit even for chunked input.
  Failed/cancelled uploads remove temporary data.
- `ComfyLTXLoopSavedCandidate` retains `candidate` as its first required widget
  and `RENDER_HANDLE` output. Append optional `source_mode` and `uploaded_video`.
  Missing options mean saved render. Validate only the active source so an unused
  placeholder or deleted inactive file cannot block execution.
- An imported handle uses existing schema v1 with `kind=imported_video`, positive
  rational FPS serialized as a string, source provenance and normalization data.
  It has no fabricated seed, generation settings or motion plan. Completed imports
  are reused by source hash and versioned normalization settings after validation.
  Unique staging directories and atomic publication prevent partial reuse.
- FFprobe must find an actual decoded video stream in a supported video container,
  excluding attached pictures and image-only inputs. Select positive avg_frame_rate,
  falling back to r_frame_rate; reject if neither is valid. FFmpeg autorotates,
  normalizes sample aspect ratio to square pixels, and normalizes timestamps/FPS.
  Preserve rational rates; VFR may duplicate/drop frames within one output period.
  At least one output frame is required. No video tensor is materialized.
- Finishing accepts candidate/imported_video, preserves PNG order/count/FPS, uses
  even dimensions and existing methods. Imported finishes use a normal playback
  preview without loop seam semantics. A completed record is published only after
  encoding, validation and interruption checks. The original is never overwritten.
- UI keeps active source and selection in serializable widgets, refreshes both
  inventories, shows filename/dimensions/duration/output FPS and normalization
  warning. Revision guards reject late list/record/upload responses. Completed
  Render updates the inactive saved candidate without switching Uploaded video.
  Upscale's two-node graph remains generation-free.

## Library research

Lookup 2026-10-26. Project: Python >=3.11, NumPy 2.2.6, Pillow 11.3.0;
ComfyUI compatibility revision `6b747c0428c343e1417219641db93a4fb7cb69ae`;
FFmpeg/aiohttp supplied by deployment, no new pins. Local FFmpeg 9.0.
Context7 resolve and query completed for `/comfy-org/comfyui` (current source),
`/websites/ffmpeg_ffmpeg-all` (current manuals), `/aio-libs/aiohttp` (current source).
Sources: [ComfyUI inputs](https://docs.comfy.org/custom-nodes/backend/datatypes),
[legacy validation](https://github.com/comfy-org/ComfyUI/blob/6b747c0428c343e1417219641db93a4fb7cb69ae/execution.py),
[server configuration](https://github.com/comfy-org/ComfyUI/blob/6b747c0428c343e1417219641db93a4fb7cb69ae/server.py),
[FFmpeg fps/autorotate/image2](https://ffmpeg.org/ffmpeg-all.html),
[aiohttp streaming uploads](https://docs.aiohttp.org/en/stable/web_quickstart.html#file-uploads).
Decision: retain legacy optional inputs/custom validation and PromptServer routes;
use request.client_max_size and explicitly count streamed bytes (multipart reads
do not enforce read() limits). Use installed FFmpeg binaries, rational fps filter,
autorotation and square-pixel scaling, with no package upgrade. Context7 is not
evidence of installed ComfyUI or GPU compatibility. No release upgrade is needed.

## Test strategy

`test_videos.py`: real FFmpeg sources for portrait, rotation, near-16:9, SAR,
fractional/VFR rates, >6 seconds and one-frame clips; decoded frame order/count,
duration, silent MP4, unchanged original, import reuse and interrupted publication.
`test_video_routes.py`: real aiohttp multipart requests for success, duplicate
names, corrupt/no-video/image inputs, limits, multiple files and traversal;
interrupted reader cleanup. `test_previews.mjs`: mode/upload/refresh, reopen,
late-response guards, normal playback and isolated queue. Existing suites retain
candidate/CLI compatibility. Editor fixture checks browser behavior only.

## Delivery and evidence

Implemented locally. See [verification ledger](../plans/2026-10-26-upload-video-upscale.md).
Real FFmpeg tests cover every supported container, portrait/rotation/SAR,
near-widescreen preservation, fractional FPS, VFR duration/content order, long and
one-frame sources, silent finishing and unchanged originals. aiohttp tests exercise
streamed requests, including chunked limits, duplicate names and cleanup. Node tests
exercise source persistence, uploads, late responses and the two-node queue.

Independent review identified POSIX cache-publication collisions, unknown SAR and
cancellation during frame hashing. Regression tests failed before their fixes and
then passed. Frame hashes now check interruption during hashing and before atomic
publication. VFR duration comes from decoded frame timestamps on disk because some
muxers underreport stream/format duration. Unknown/nonpositive SAR means square
pixels. Cache publication accepts EEXIST/ENOTEMPTY and validates the winner.

Known minor: identical bytes uploaded under different names reuse the first
import's filename/ID in cached provenance; the hash identifies the same content.
Selected source widgets still retain the chosen upload ID. Installed ComfyUI
conversion, real AI/GPU upscale and visual quality remain pending. The editor
fixture served and its controls were inspected in Chrome; automated native file
selection failed (extension file-URL permission), so end-to-end browser upload
was not qualified. Production upload behavior is covered by the real HTTP tests.
