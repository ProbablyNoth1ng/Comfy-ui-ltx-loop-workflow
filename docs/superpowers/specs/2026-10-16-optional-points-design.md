# Optional character and background points design

Date: 2026-10-16. Status: implemented in source; deployment and visual qualification pending.
Product requirements: [P-05 and P-14](../../product-spec.md).

## Intent and scope

The owner may guide motion with text alone or selectively use saved character and
background tracks. Disabling a group keeps its points for another attempt. The
existing LTX Motion Track graph and official baseline remain unchanged.

## Behavior and acceptance criteria

- Persist `use_character_points` and `use_background_points` booleans in the motion
  plan, defaulting to true when absent in older plans. Background tracks also require
  nonblank Background motion. Blank background text never discards saved points.
- Review and preparation apply to groups with active enabled points. Switching group
  selection invalidates a reviewed plan; re-enabling requires renewed review and
  current preparation. Active background tracks require a moving enabled point.
- When no points are active, Render builds a fresh plan from the current image and
  settings, marks review `not_required`, sends `[]` to the graph and never calls Qwen.
  Character and nonblank background text remain in the render prompt. Candidate
  persistence retains this plan and review state.
- Active points still require a valid prepared and reviewed plan. A stale image,
  point edit or changed active-group settings blocks Render.

## Architecture and contracts

`motion.py` owns group activation, track filtering, preparation and review rules.
`staged_comfy.py` adds optional boolean node inputs, constructs the no-point plan,
and persists it through the existing `motion_plan` output. The editor exposes two
switches and permits direct Render when no points are active. The workflow builder
updates only the user hint and generated editable workflow; the official baseline
is untouched. Existing widget order remains stable because inputs are optional.

## Library research

Looked up 2026-10-16. Project uses the pinned official LTX-2.5 Motion Track graph;
the installed ComfyUI-LTXVideo revision remains unqualified. Context7 ID
`/lightricks/comfyui-ltxvideo` documents `LTXVDrawTracks`; its generated API
description does not establish the empty-list result. The [official source](https://github.com/Lightricks/ComfyUI-LTXVideo/blob/master/sparse_tracks.py)
at master explicitly returns a black guide frame for an empty parsed track list.
Compatibility decision: keep the existing graph; verify installed revision and
downstream frame behavior during deployed qualification.

## Test strategy

`test_motion.py` covers four group combinations, legacy defaults, stale active
preparation and review invalidation. `test_stages.py` proves direct Render sends
`[]`, avoids Qwen, retains text and produces a persistable plan. Editor Node tests
cover switches, save/reopen and direct queue. Existing stage and candidate tests
cover isolation and persistence. Record red/green results in the plan.

## Delivery and evidence

The [implementation plan](../plans/2026-10-16-optional-points.md) records the
red/green cycle and local checks. Installed ComfyUI conversion, GPU inference and
anime quality remain pending.
