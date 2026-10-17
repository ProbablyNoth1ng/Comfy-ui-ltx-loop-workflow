# Comfy LTX Loop code map

Updated: 2026-10-17. Read this before locating code. Update it in the same change
whenever files/directories are added, deleted, renamed or moved, or module ownership
changes. Confirm details against source; this is navigation, not a substitute for code.

## Where to look

| Work | Start here | Tests / reference |
| --- | --- | --- |
| Product intent and accepted behavior | `docs/product-spec.md` | `docs/superpowers/specs/2026-10-09-comfy-ltx-loop-rebrand-design.md`, baseline and render designs |
| Development workflow and new specs | `AGENTS.md`, `docs/superpowers/README.md` | Workflow design and plan under `docs/superpowers/` |
| Motion plans, roles, groups, review, timing and canvas mapping | `comfy_ltx_loop/motion.py` | `tests/test_motion.py`, `tests/test_semantic_points.py` |
| Strict render modes, point-linked source masks and protected-pixel compositing | `comfy_ltx_loop/motion.py`, `comfy_ltx_loop/candidates.py` | `tests/test_motion.py`, `tests/test_candidates.py` |
| Optional point-group selection and direct Render | `comfy_ltx_loop/motion.py`, `staged_comfy.py`, editor web module | `tests/test_motion.py`, `tests/test_stages.py`, `tests/test_editor_semantics.mjs` |
| Automatic character/background point proposals and model cleanup | `comfy_ltx_loop/vision.py` | `tests/test_vision.py` |
| Prepare/Render/Upscale backend node interfaces | `comfy_ltx_loop/staged_comfy.py` | `tests/test_stages.py` |
| Points UI, background controls, review and previews | `comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js` | `tests/test_editor_semantics.mjs`, `tests/test_previews.mjs`, `tests/editor_harness.py` |
| Coordinate mapping and letterboxing | `comfy_nodes/comfy_ltx_loop/web/geometry.mjs` | `tests/test_editor_geometry.mjs` |
| Stage pruning and global Run chooser/queue guards | `comfy_nodes/comfy_ltx_loop/web/stages.mjs`, `queue_control.mjs` in the same directory | `tests/test_stages.mjs`, `tests/test_queue_control.mjs` |
| Saved candidates, MP4 encoding, Fast/AI finishing and resolution | `comfy_ltx_loop/candidates.py` | `tests/test_candidates.py`, `tests/test_resolution_integration.py` |
| Review/candidate HTTP endpoints | `comfy_ltx_loop/comfy_routes.py` | Backend stage tests and editor fixture |
| Official and adapted LTX graph | `workflows/`, `tools/build_comfy_ltx_loop_workflow.mjs` | `tests/test_motion_workflow.mjs`, `docs/qualification.md` |
| Cloud install, ComfyUI compatibility and model snapshots | `cloud/install.py` | `tests/test_cloud_install.py`, `tests/test_vision_install.py` |
| RunPod launch adapter and start-command generation | `cloud/runpod_entrypoint.py`, `tools/build_runpod_command.py` | `tests/fixtures/`, `docs/runpod-autoinstall.md` |
| Deployed GPU proof and visual acceptance | `tools/qualify_ltx.py`, `docs/qualification.md` | `evidence/`; actual GPU evidence remains pending |
| Existing CLI, approvals and regional workflow | `comfy_ltx_loop/cli.py`, `project.py`, `jobs.py`, `regional.py` | `tests/test_workflow.py`, `tests/test_operations.py`, `docs/legacy-cli.md` |

## Current change documents

- `docs/superpowers/specs/2026-10-17-qwen2b-points-design.md` and
  `docs/superpowers/plans/2026-10-17-qwen2b-points.md`: selectable 2B proposals,
  additive pinned cloud snapshot and verification.
- `docs/superpowers/specs/2026-10-17-strict-motion-areas-design.md` and
  `docs/superpowers/plans/2026-10-17-strict-motion-areas.md`: strict point areas,
  source-backed candidate persistence and protected PNG finishing.
- `docs/superpowers/specs/2026-10-08-exact-16x9-render-design.md`: near-16:9
  crop contract, Pillow compatibility research and verification boundary.
- `docs/superpowers/plans/2026-10-08-exact-16x9-render.md`: test-first
  implementation ledger for exact export and finish dimensions.
- `docs/superpowers/specs/2026-10-08-faster-finishing-design.md`: three finishing
  methods, new/old node contracts and library research.
- `docs/superpowers/plans/2026-10-08-faster-finishing.md`: finishing implementation
  and verification ledger.
- `docs/superpowers/specs/2026-10-09-comfy-ltx-loop-rebrand-design.md` and
  `docs/superpowers/plans/2026-10-09-comfy-ltx-loop-rebrand.md`: canonical naming,
  breaking-compatibility boundary and delivery evidence.
- `docs/superpowers/specs/2026-10-16-optional-points-design.md` and
  `docs/superpowers/plans/2026-10-16-optional-points.md`: optional track groups,
  direct no-point Render and verification.

## Complete maintained project tree

Every maintained file is listed below. Generated/runtime areas are described in
the next section. Tree comments explain ownership rather than guarantee behavior.

```text
anime-loop-research/
├── .gitignore
├── AGENTS.md                         Agent workflow and project constraints
├── codemap.md                        This maintained navigation map
├── pyproject.toml                    Python package metadata and dependency pins
├── README.md                         Primary ComfyUI usage and documentation entry
├── REPORT.md                         Historical research report
├── comfy_ltx_loop/
│   ├── __init__.py                   Package initialization
│   ├── __main__.py                   python -m comfy_ltx_loop entry
│   ├── assets.py                     Checked model-weight caching
│   ├── benchmark.py                  CLI rendering/transfer benchmark
│   ├── candidates.py                 Persistent records, previews and Fast/AI finishing
│   ├── cli.py                        Existing CLI commands
│   ├── comfy.py                      Legacy node/export integration and node registry
│   ├── comfy_routes.py               Same-origin review and candidate endpoints
│   ├── environment.py                Environment revision/lock operations
│   ├── examples.py                   CLI example generation
│   ├── jobs.py                       CLI render/checkpoint/review/accept operations
│   ├── motion.py                     Normalized plans, transforms, semantics and review
│   ├── project.py                    CLI project validation, hashes and approval state
│   ├── queue.py                      CLI ComfyUI submission receipts and status
│   ├── regional.py                   Existing regional fallback preparation/finishing
│   ├── renderer.py                   Existing CPU animation renderer
│   ├── staged_comfy.py               Primary staged ComfyUI nodes
│   └── vision.py                     Local Qwen proposals and resource cleanup
├── cloud/
│   ├── bootstrap.sh                  Cloud installation entry
│   ├── install.py                    Nodes, compatibility, dependencies and model install
│   ├── runpod_entrypoint.py          Official launcher patch adapter
│   └── start.sh                      Cloud ComfyUI launch entry
├── comfy_nodes/
│   └── comfy_ltx_loop/
│       ├── __init__.py               ComfyUI custom-node/web registration
│       └── web/
│           ├── comfy_ltx_loop.js       Editor UI, stage actions and previews
│           ├── geometry.mjs          Display/source coordinate transforms
│           ├── queue_control.mjs     Run interception and unsafe-prompt guards
│           └── stages.mjs            Stage-specific graph pruning
├── docs/
│   ├── cloud-setup.md                Manual cloud installation instructions
│   ├── implementation-plan.md        Original implementation brief/history
│   ├── legacy-cli.md                 Existing CLI documentation
│   ├── product-spec.md               Living owner-facing product specification
│   ├── qualification.md              Dated evidence and pending GPU/visual acceptance
│   ├── runpod-autoinstall.md          Automatic RunPod setup and storage/launch guidance
│   ├── smarter-points-progress.md    Semantic-point implementation ledger
│   └── superpowers/
│       ├── README.md                 Spec index and design/plan writing outlines
│       ├── plans/
│       │   ├── 2026-10-04-comfy-ltx-loop-global-run.md
│       │   ├── 2026-10-04-comfy-ltx-loop-staged-points.md
│       │   ├── 2026-10-08-exact-16x9-render.md
│       │   ├── 2026-10-08-faster-finishing.md
│       │   ├── 2026-10-08-project-workflow.md
│       │   ├── 2026-10-09-comfy-ltx-loop-rebrand.md
│       │   ├── 2026-10-16-optional-points.md
│       │   ├── 2026-10-17-qwen2b-points.md
│       │   └── 2026-10-17-strict-motion-areas.md
│       └── specs/
│           ├── 2026-10-08-comfy-ltx-loop-baseline-design.md
│           ├── 2026-10-08-exact-16x9-render-design.md
│           ├── 2026-10-08-faster-finishing-design.md
│           ├── 2026-10-08-project-workflow-design.md
│           ├── 2026-10-09-comfy-ltx-loop-rebrand-design.md
│           ├── 2026-10-16-optional-points-design.md
│           ├── 2026-10-17-qwen2b-points-design.md
│           └── 2026-10-17-strict-motion-areas-design.md
├── evidence/
│   ├── comfy-local-validation.json   Historical local validation record
│   ├── flf.json                      Reference workflow evidence
│   ├── imageops-tree.txt             Reference image-operations inventory
│   ├── inpaint.json                  Reference workflow evidence
│   ├── motion.json                   Reference motion workflow evidence
│   ├── tracks.py                     Reference Motion Track implementation
│   └── two_stage.json                Reference two-stage workflow evidence
├── examples/                         Existing CLI source/mask/project fixtures
│   ├── calm-wind/
│   │   ├── guard.png
│   │   ├── mask.png
│   │   ├── project.json
│   │   ├── roots.png
│   │   ├── source.png
│   │   ├── support.png
│   │   └── weight.png
│   ├── rainy-window/
│   │   ├── guard.png
│   │   ├── mask.png
│   │   ├── project.json
│   │   ├── roots.png
│   │   ├── source.png
│   │   ├── support.png
│   │   └── weight.png
│   └── sunset-field/
│       ├── guard.png
│       ├── mask.png
│       ├── project.json
│       ├── roots.png
│       ├── source.png
│       ├── support.png
│       └── weight.png
├── runpod/
│   ├── bootstrap.sh                  RunPod bootstrap entry
│   └── start.sh                      RunPod launch entry
├── tests/
│   ├── editor_harness.py             Local HTTP editor fixture; simulated queues
│   ├── test_candidates.py            Candidate persistence and finishing
│   ├── test_cloud_install.py         Cloud install and launcher contracts
│   ├── test_editor_geometry.mjs      Coordinate/letterboxing checks
│   ├── test_editor_semantics.mjs     Semantic roles, groups and editor persistence
│   ├── test_motion.py               Motion validation, transforms and review
│   ├── test_motion_workflow.mjs      Adapted graph structure checks
│   ├── test_operations.py           CLI/environment/asset operations
│   ├── test_previews.mjs             Candidate UI and preview behavior
│   ├── test_queue_control.mjs       Global Run interception and queue safety
│   ├── test_resolution_integration.py  Orientation/resolution finishing preservation
│   ├── test_rebrand.py              Canonical package/CLI/custom-node contract
│   ├── test_rebrand_inventory.mjs   Legacy-brand path/content regression guard
│   ├── test_semantic_points.py      Semantic parsing and roles
│   ├── test_stages.mjs              Frontend stage isolation
│   ├── test_stages.py               Backend stage contracts and groups
│   ├── test_vision.py               Local vision dispatch/failure/cleanup contracts
│   ├── test_vision_install.py       Snapshot install/cache/manifest contracts
│   ├── test_workflow.py             Existing CLI workflows
│   └── fixtures/
│       └── runpod-start-e8505fe1.sh  Extracted provider launcher fixture
├── tools/
│   ├── build_comfy_ltx_loop_workflow.mjs     Regenerate adapted graph from official workflow
│   ├── build_runpod_command.py       Generate RunPod start-command JSON
│   └── qualify_ltx.py               Observe real ComfyUI/GPU qualification runs
└── workflows/
    ├── comfy-ltx-loop-motion.json          Primary editable ComfyUI workflow
    ├── ltx-2.5-motion-track.official.json  Unchanged official qualification baseline
    ├── workflow-a.api.json          Existing CLI API graph
    └── workflow-a.json              Existing CLI editable graph
```

## Generated, local and external areas

- `outputs/`: ignored local frames, videos, reviews and generated RunPod commands.
- `benchmarks/`, `environment.lock.json`: ignored benchmark/environment records.
- `.venv/`, `__pycache__/`, `*.egg-info/`: ignored Python environment/cache/build data.
- `.git/`: repository metadata; do not inventory internal files.
- An installed ComfyUI checkout, models and `ComfyUI/output/comfy-ltx-loop/` live on
  the deployment host, outside this source tree. Candidate directories contain
  records, raw/exported frames and preview videos.
- Context7's server/credential/rule live in user-level `~/.codex/config.toml` and
  `~/.codex/AGENTS.md`; its installed skill is under `~/.agents/skills/context7-mcp/`.
  These are external configuration, not project files. Never copy credentials here.

Inventory the maintained tree with:

```powershell
rg --files --hidden -g '!.git/**' -g '!outputs/**' -g '!benchmarks/**' -g '!.venv/**' -g '!**/__pycache__/**' -g '!**/*.egg-info/**' -g '!environment.lock.json'
```

When adding a design/plan, update the tree and `docs/superpowers/README.md` index.
When changing ownership, update both the tree comment and the navigation table.
