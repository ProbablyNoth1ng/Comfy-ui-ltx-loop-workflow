# Lightweight Qwen point proposals

Date: 2026-10-17. Status: implemented locally; host/GPU/visual qualification pending.
Product requirements: [P-15](../../product-spec.md#user-journey-and-requirements),
with P-02, P-03, P-05 and P-10 preserved.

## Intent and acceptance

Add `local Qwen3-VL 2B` to the existing preparation selector. From a bundled model
path it selects `models/Qwen3-VL-2B-Instruct`. Preserve explicit custom paths,
existing option strings, widget slots, stage buttons and the default selection.
All three Prepare actions use the selected snapshot for their model-enabled
groups. Keep the character 16–24 useful visible point guideline, background
instructions, semantic parsing, partial feedback, failure preservation and cleanup.
Suggestions still require review. Switching models invalidates review and affected
group preparation; preparing one group cannot refresh the other group's provenance.

Automatic cloud setup installs the 2B snapshot plus the selected larger snapshot.
The larger selection remains Qwen3.5-9B for new installations and the existing
choice (including Qwen3-VL-8B-Instruct) otherwise. `--vision-model` and its environment
variable continue to select the larger model. Do not change official LTX assets,
inference parameters, dependency ranges or saved workflow copies.

## Architecture and compatibility

- `staged_comfy.py`: append the selector option; route it through `analyze` with
  the same prompts and model path. Leave required and optional widget order intact.
- Editor JS: map the three named automatic modes to their bundled paths; retain
  custom paths and configure/reopen behavior. Existing preparation/review guards
  enforce stale state, including background model provenance.
- `vision.py`: reuse `qwen3_vl` config dispatch, local-only processor/model loading,
  parsing and exception cleanup unchanged.
- `cloud/install.py`: retain the larger-model signatures and legacy migration.
  Ensure the additive 2B snapshot on both cache-hit and full-download paths.
  Its own `vision-Qwen3-VL-2B-Instruct-plan.json` pins remote resolution before
  downloading, and `vision-Qwen3-VL-2B-Instruct.json` records verified SHA256s.
  Reuse complete snapshots without remote resolution. Recover missing/truncated
  files from the recorded immutable revision, including after interrupted downloads.
  Force a new download for an existing file with a known wrong size, bypassing
  Hub local metadata that can otherwise keep returning the incomplete file.
  Preserve larger-model provenance, per-selection ready caches and workflow defaults.
  Shared download verification may be extracted without changing its contracts.

## Library research

Lookup: 2026-10-17. Project pin: `transformers>=5.2,<6` (vision extra),
`accelerate>=1.10,<2`; deployment ComfyUI compatibility revision remains
`6b747c0428c343e1417219641db93a4fb7cb69ae`; LTX revision remains host-selected.
Context7 resolved official Transformers docs to
`/websites/huggingface_co_transformers_main` (High reputation); the Qwen3-VL query
had no matches and the narrower multimodal query returned unrelated LayoutLMv2
examples. This is insufficient Qwen coverage, so official sources are the fallback:

- [2B model card](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct)
- [2B config](https://huggingface.co/Qwen/Qwen3-VL-2B-Instruct/raw/main/config.json)

The card demonstrates `Qwen3VLForConditionalGeneration` and `AutoProcessor`, auto
dtype/device placement, image/text chat templates, generation and trimming input
tokens before decoding. Config declares `model_type=qwen3_vl` and that architecture.
This matches the existing loader, with local-only loading retained. No dependency
upgrade or latest-release claim is needed. Actual runtime compatibility remains a
host qualification item.

Recovery lookup on the same date resolved Context7 to
`/huggingface/huggingface_hub` (High reputation, official repository). The Hub
package is supplied transitively by Transformers and has no separate project
version pin. Queries confirmed immutable full-length revisions and force-download
support. [Official download source](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/file_download.py)
and [local metadata](https://github.com/huggingface/huggingface_hub/blob/main/src/huggingface_hub/_local_folder.py)
show the existing-file fast path. Compatibility decision: pass `force_download`
only when a destination file already exists with an incorrect recorded size;
complete snapshot cache hits keep their existing lightweight checks.

## Tests and evidence boundary

`tests/test_stages.py`: selector compatibility, per-target model dispatch, point
groups/review, model switching, failed reprepare and stale untouched groups.
`tests/test_editor_semantics.mjs`: bundled mapping, review invalidation, blocked
acceptance until reprepare, saved and custom paths.
`tests/test_vision.py`: existing family dispatch/point instruction/cleanup coverage;
extend it to exercise Qwen3-VL failures too, without changing production behavior.
`tests/test_vision_install.py`: both larger choices plus additive 2B, independent
pins/hashes, cache reuse, legacy migration and interrupted/truncated recovery.
Use real disk manifests with a fake Hub boundary; no real weight downloads in tests.

Run full Python/Node suites and diff checks. Local doubles do not measure VRAM,
point placement quality, installed ComfyUI conversion or actual inference. Those
remain pending on a host. Execution/results live in the
[plan](../plans/2026-10-17-qwen2b-points.md).

## Delivered behavior

The appended selector dispatches all three Prepare targets through the existing
Qwen3-VL loader and preserves failure feedback, manual correction and review.
Bundled paths map by mode; custom paths, saved slots and defaults remain intact.
Cloud setup ensures the additive 2B snapshot on cache hits and full installs,
with separate pinned plan/provenance and a forced fetch for a known truncated
destination. Larger selection/caches, official LTX and dependency pins are retained.
An independent review found the Hub metadata edge; a new regression reproduced
it before the fix, then all 10 installer tests passed. No host performance or
quality claim follows from local tests. Final full suites passed 107 Python and
42 Node tests; documentation links/inventory and `git diff --check` passed.
