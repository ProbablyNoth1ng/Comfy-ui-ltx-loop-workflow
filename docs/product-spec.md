# Comfy LTX Loop product specification

Updated: 2026-10-17.

This is the living product agreement for the owner. Technical designs and task
plans are indexed in [Superpowers documents](superpowers/README.md).
[The codemap](../codemap.md) explains where the implementation lives.

## Purpose

Turn one anime illustration into a short, silent animation in ComfyUI. The owner
can direct character and selected scenery motion, correct control points before
generation, inspect the loop and finish a saved render at a higher resolution.

The desired result preserves recognizable faces, clean linework, the original
composition and a stable camera. These are visual acceptance goals; model guidance
does not guarantee them. Real anime and GPU qualification is still pending.

## User journey and requirements

| ID | Requirement and acceptance criteria | Delivery status |
| --- | --- | --- |
| P-01 | Load exactly one source image. Preserve orientation and aspect ratio through preparation, rendering and finishing, except the small centered crop required by P-11. | Implemented; deployment qualification pending |
| P-02 | Enter character motion and optionally requested parts. Prepare suggestions with local Qwen3.5, local Qwen3-VL or manual editing. Automatic failures show actionable feedback and leave manual correction available. Useful visible suggestions survive partial responses; hidden anatomy is omitted. | Implemented; real model accuracy pending |
| P-03 | Enter background motion to enable scenery animation. Choose Model or Manual; prepare Character, Background or both. Each preparation changes its own group. Clearing background motion excludes background tracks and retains saved points. Failed automatic preparation preserves existing points. | Implemented; deployed scenery render pending |
| P-04 | Review/edit points on the source image. Filter Character, Background or All; hidden points cannot be selected. Choose the group for new points. Add, move, delete or disable points, edit labels/objects/roles/reasons/strengths and inspect trajectories. Moving points are green, stationary anchors blue, disabled points gray; character points are circles and background points squares. Each visible group shows its true count and preserves original point numbers. In strict mode, the selected moving point has a translucent source-area overlay which can be painted, erased or cleared through the letterboxed source mapping. | Repair implementing; installed frontend qualification pending |
| P-05 | Accept point review before Render when points are active. Changed image clears groups; changed instructions or preparation settings require preparing an affected active group again. Point edits and group switches invalidate review. Timing/canvas changes keep normalized paths and require renewed review when points are active. Active background points need an enabled moving background point. Strict review reports the unresolved per-point area blocker and preserves it until corrected; accepted review persists through save/reopen. | Repair implementing; installed frontend qualification pending |
| P-06 | Run offers an explicit choice of Prepare character, Prepare background, Prepare both, Render or Upscale. One choice queues one isolated stage. Prepare cannot generate; Render cannot upscale; Upscale reads only a saved candidate. Cancel queues nothing. | Implemented; deployed conversion/queue qualification pending |
| P-07 | Render with the official LTX-2.5 single-stage Motion Track pipeline. Show continuous and forward seam previews, allow another seed/candidate, and retain original lossless frames. Returning trajectories guide closure; the owner checks the seam. | Implemented; GPU and visual acceptance pending |
| P-16 | Choose Free motion (default) or Only pointed parts. Strict mode accepts only current reviewed masks belonging to enabled moving points in active groups; it blocks an empty selection with “Add or enable a moving point, or switch to Free motion.” It identifies missing or stale areas by point number and label. Source pixels outside the approved areas remain byte-identical in saved PNG frames, including after finishing. | Repair implementing; renderer/GPU qualification pending |
| P-17 | Place new points through Add character point and Add background point. Strict Prepare proposes SAM 2.1 Small areas after point preparation. Update motion areas retains point identity, roles, positions and paths and updates only missing/stale areas. Point, source, area, trajectory or mode changes require a new acceptance; label changes require review but retain a current area. | Repair implementing; installed frontend qualification pending |
| P-08 | Select original saved candidates after reopening; automatically select the newest completed render and refresh the list when requested. Preserve reviewed points in the saved workflow. | Implemented; real ComfyUI restart qualification pending |
| P-09 | Optionally finish a selected candidate at short sides of 1080, 1440 or 2160 pixels. Preserve aspect ratio, even dimensions, frame count, FPS, timing and original candidate files. The existing Original AI Upscale node defaults to 1440; new workflows use the P-12 default. Save a silent MP4 with lossless frames alongside it. | Implemented in source; GPU and temporal-flicker qualification pending |
| P-10 | Support documented cloud installation and retain the existing CLI. Record deployment/model versions and actual runtime evidence before promising supported hardware or performance. | Implemented setup paths; provider qualification pending |
| P-11 | For source content whose long-to-short ratio is within 2% of 16:9, save exact 16:9 exported render frames after generation-canvas padding is removed: 1280x720 at the standard 720-pixel short side, or 720x1280 for portrait. Center-crop only the exported/finished frame; raw generated frames and the reviewed canvas remain unchanged. Finishing those candidates at 1080p, 1440p and 4K saves 1920x1080, 2560x1440 and 3840x2160 (portrait counterparts included). Sources outside tolerance retain their existing aspect ratio behavior. | Implemented locally; GPU and visual qualification pending |
| P-12 | After Render, finish any saved candidate again with Fast (FFmpeg Lanczos), Balanced AI (installed anime weights in supported FP16 with adaptive tiles), or Original AI (existing Real-ESRGAN path). New workflows default to Fast at 1080p; existing Upscale nodes retain Original AI and 1440p defaults. Every finish keeps frame count, FPS, silent MP4, lossless frames, aspect/crop rules and the candidate unchanged, with its method recorded. | Implemented in source; Python, installed ComfyUI, GPU speed and visual verification pending |
| P-13 | Use only the Comfy LTX Loop public identity: `comfy-ltx-loop` for commands and hyphenated paths, `comfy_ltx_loop` for Python/import paths, `ComfyLTXLoop…` for node types, and `Comfy LTX Loop` for display text. Previous names, commands, saved workflows, records, routes, output paths and environment variables are intentionally unsupported. | Implemented locally; deployment/GPU qualification unchanged and pending |
| P-14 | Choose independently whether character and background points guide the next Render. Switching a group off preserves its points; older workflows start with both groups on. Render accepts either group, both or no active points. With no active points, load an image, set character and optional background motion text, and Render directly without Prepare, Qwen or point review. Text still guides motion; a saved candidate records that point review was unnecessary. Re-enabling points requires renewed review and only active groups require current preparation. | Implemented in source; installed ComfyUI and visual qualification pending |
| P-15 | Choose local Qwen3-VL 2B for character, background or combined point preparation. It uses the existing point instructions, including the character 16–24 useful visible point guideline, manual correction and explicit review. Changing models makes affected preparation and review stale. Automatic installation adds 2B alongside the selected larger model: existing installations keep their choice; new ones still default to Qwen3.5-9B. Saved workflows, widget order and the official LTX baseline remain compatible. | Implemented locally; GPU memory, real point quality and deployed ComfyUI checks pending |

"Implemented" describes repository behavior and existing evidence. It does not
mean this session reran all tests or that a production GPU run was accepted.
See [qualification](qualification.md) for dated checks and unresolved deployment work.

## Current defaults

| Setting | Default |
| --- | --- |
| Duration / playback FPS | 6 seconds / 24 FPS |
| Seed / motion strength | 42 / 0.01 |
| Generation short side | Near 720 pixels, with internal alignment padding |
| Character preparation | Local Qwen3.5 (`Qwen/Qwen3.5-9B`) |
| Background preparation | Model; animation enabled only by nonblank background motion |
| New workflow finishing | Fast at 1080 pixels; existing Upscale nodes default to Original AI at 1440 pixels |
| Camera intent | Stationary |
| Default generated / playback frames | 145 / 144 |

## Quality acceptance

Before accepting a real output, inspect repeated playback and its forward seam
for face identity, hair motion and overlap, stationary anchors, camera/background
drift, line preservation and flicker. Compare the higher-resolution finish to
the original render. A numerical closure measurement supports review and cannot
replace it. Retry visibly poor candidates; never automatically reverse frames
to manufacture ping-pong playback.

No supported GPU minimum, measured inference runtime or guaranteed seamless loop
is established. Cloud and real anime checks remain in [qualification](qualification.md).
Strict masks and source compositing belong to other workflows and are not part
of the current LTX animation journey.

## How we implement changes

Every implementation updates this product spec and its corresponding technical
spec before code and again as behavior or evidence changes. New requirements get
stable IDs continuing after P-10; existing IDs retain their meaning.

Use Superpowers to clarify requirements, design and plan. Check relevant current
library documentation through Context7 during planning. Write and run a failing
behavioral test first, implement code to make it green, then refactor and verify.
Update [codemap.md](../codemap.md) whenever project structure changes.

## Delivery notes

- 2026-10-17: Added agent-only image-to-video prompt assistance. When an owner
  supplies an inspectable image and asks for animation-prompt help, the agent runs
  an adaptive, one-question-at-a-time interview and returns English positive,
  negative and background prompts for the existing LTX-2.5 workflow. This changes
  no product behavior, model setting, point preparation or rendering path. See the
  [workflow design](superpowers/specs/2026-10-08-project-workflow-design.md) and
  [plan](superpowers/plans/2026-10-08-project-workflow.md).

- 2026-10-17: P-15 adds a lightweight point proposal choice and a separately pinned
  automatic-install snapshot, including recovery of truncated Hub cache files.
  Local regressions and independent code review completed; GPU memory, model
  accuracy and deployed ComfyUI checks remain pending. See the [2B design](superpowers/specs/2026-10-17-qwen2b-points-design.md)
  and [implementation plan](superpowers/plans/2026-10-17-qwen2b-points.md).

- 2026-10-16: P-14 adds optional character/background track groups and direct
  text-guided Render without active points. Local Python and Node tests passed;
  the fixture served the editor over HTTP. Installed ComfyUI, GPU and visual checks
  remain pending. See the [optional points design](superpowers/specs/2026-10-16-optional-points-design.md)
  and [plan](superpowers/plans/2026-10-16-optional-points.md).

- 2026-10-09: Completed the intentional breaking rebrand to Comfy LTX Loop. It replaces
  every tracked legacy identifier and persisted key; no compatibility aliases or
  data migration are provided. Python, Node and fixture verification passed;
  deployment/GPU qualification is unchanged and pending. See the [rebrand design](superpowers/specs/2026-10-09-comfy-ltx-loop-rebrand-design.md).
- 2026-10-08: Added Fast, Balanced AI and Original AI finishing choices to the
  editable workflow and retained the old Upscale node contract. Node tests and an
  FFmpeg command probe passed; this Windows checkout has no Python runtime, so
  Python regression tests remain unrun. No saved LTX candidate or local GPU is
  available for timing/visual comparison. See the [faster finishing design](superpowers/specs/2026-10-08-faster-finishing-design.md).
- 2026-10-08: Added centered near-16:9 export/finish cropping. Local regression
  coverage includes an independently constructed legacy 1290x720 candidate; FFmpeg
  probes confirmed 1280x720 render and 1920x1080 finish MP4s. GPU and visual
  qualification remain pending. See the [exact 16:9 render design](superpowers/specs/2026-10-08-exact-16x9-render-design.md).
- 2026-10-08: Established this baseline from current source, README and existing
  qualification records. Added owner/agent specs, maintained code navigation,
  mandatory test-first rules and Context7 research configuration. This setup changes
  the development workflow; product requirements P-01 through P-10 retain their current scope.
  See the [workflow design and verification](superpowers/specs/2026-10-08-project-workflow-design.md).
- Current priorities requiring external evidence: installed ComfyUI conversion and
  queues, actual Qwen placement and memory release, LTX render quality, seams, and
  all supported finishing sizes. There is no active feature implementation plan
  selected by this baseline.
