# Specifications and implementation plans

Read [the product spec](../product-spec.md) for owner-facing behavior,
[the codemap](../../codemap.md) to locate code, and [agent rules](../../AGENTS.md)
for the required workflow.

## Current specifications

| Document | Purpose |
| --- | --- |
| [Uploaded video Upscale design](specs/2026-10-26-upload-video-upscale-design.md) | Personal video storage, timing normalization and compatible source selection |
| [Uploaded video Upscale plan](plans/2026-10-26-upload-video-upscale.md) | Implementation and verification ledger |
| [Comfy LTX Loop baseline](specs/2026-10-08-comfy-ltx-loop-baseline-design.md) | Current architecture, contracts, dependencies and test ownership |
| [Project workflow design](specs/2026-10-08-project-workflow-design.md) | Product/technical specs, Context7, test-first work and codemap maintenance |
| [Exact 16:9 render design](specs/2026-10-08-exact-16x9-render-design.md) | Export and finishing crop rule for near-16:9 sources |
| [Faster finishing design](specs/2026-10-08-faster-finishing-design.md) | Three post-Render finishing methods and legacy node compatibility |
| [Faster finishing plan](plans/2026-10-08-faster-finishing.md) | Test-first implementation and verification ledger |
| [Project workflow plan](plans/2026-10-08-project-workflow.md) | Setup tasks and verification evidence |
| [Comfy LTX Loop rebrand](specs/2026-10-09-comfy-ltx-loop-rebrand-design.md) | Breaking replacement of all legacy naming and persisted identifiers |
| [Comfy LTX Loop rebrand plan](plans/2026-10-09-comfy-ltx-loop-rebrand.md) | Rebrand delivery and verification ledger |
| [Optional points design](specs/2026-10-16-optional-points-design.md) | Group switches and direct Render without point review |
| [Optional points plan](plans/2026-10-16-optional-points.md) | Test-first implementation and verification ledger |
| [Lightweight Qwen proposals](specs/2026-10-17-qwen2b-points-design.md) | Selectable 2B proposals and additive pinned installation |
| [Lightweight Qwen plan](plans/2026-10-17-qwen2b-points.md) | Test-first implementation and verification ledger |
| [Strict motion areas design](specs/2026-10-17-strict-motion-areas-design.md) | Free/strict render behavior and source-pixel protection |
| [Strict motion areas plan](plans/2026-10-17-strict-motion-areas.md) | Strict-area implementation ledger |

## Existing implementation history

- [Staged points plan](plans/2026-10-04-comfy-ltx-loop-staged-points.md)
- [Global Run plan](plans/2026-10-04-comfy-ltx-loop-global-run.md)
- [Exact 16:9 render plan](plans/2026-10-08-exact-16x9-render.md)
- [Original implementation brief](../implementation-plan.md)
- [Semantic points ledger](../smarter-points-progress.md)
- [Qualification evidence and pending checks](../qualification.md)

Historical plans predate the paired-spec workflow. Preserve them as history; use
current source, the baseline and dated evidence to determine delivery status.

## For every new implementation

Use Superpowers brainstorming to resolve requirements. Update the living product
spec, then create or extend a technical design and write a plan for multi-step work.
Research relevant library contracts through Context7 before choosing APIs.
Keep the product spec, design and plan synchronized as decisions change.

Before each production behavior change: write the test, run it and confirm the
expected behavioral failure, implement the smallest passing change, rerun, then
refactor. Record evidence in the plan. Documentation/configuration changes use
document or connection checks instead. Update the codemap in the same change
whenever files or module ownership change.

## Product spec conventions

Keep goals and user journeys in `docs/product-spec.md`. Use stable requirement IDs,
plain-language acceptance criteria and delivery statuses. Separate implemented
repository behavior from deployment and visual qualification. Add a dated delivery
note linking the technical design when a feature changes. Never turn an assumption
or an unrun check into a completion claim.

## Technical design outline

Save as `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`. Scale detail to scope;
small changes may extend the existing design. Fill the outline before implementation:

```markdown
# <Topic> design
Date: <date>. Status: <draft / implementing / implemented; verification gaps>.
Product requirements: <links to IDs in docs/product-spec.md>.

## Intent and scope
User outcome, included work, assumptions and explicit constraints.
## Behavior and acceptance criteria
Concrete inputs, outcomes, edge cases and stable requirement IDs.
## Architecture and contracts
Affected modules, interfaces, data/persistence, errors and compatibility.
## Library research
Lookup date; project pins; Context7 ID/documentation version; source links;
official release evidence when freshness matters; chosen compatibility approach.
## Test strategy
Map criteria to test files/names/assertions and expected initial failures.
Identify deployment/visual checks that automated tests cannot prove.
## Delivery and evidence
Implemented behavior, actual commands/results, remaining checks and plan link.
```

## Implementation plan outline

Use Superpowers `writing-plans`. Save as
`docs/superpowers/plans/YYYY-MM-DD-<topic>.md` and link the technical design:

```markdown
# <Topic> Implementation Plan
> For agentic workers: use superpowers:executing-plans, or the execution
> workflow explicitly selected by the owner. Track steps with checkboxes.
Goal: <observable outcome>.
Architecture: <approach>.
Tech stack: <relevant versions>.
Spec: <relative link to technical design>.

## Constraints and review focus
Compatibility, failure cases and boundaries from the spec.
## Task 1: <independently reviewable change>
Files: <production, test and spec paths>.
Interfaces: <exact changed contract when relevant>.
- [ ] Write <test name> asserting <acceptance outcome>.
- [ ] Run <exact command>; observe <expected behavioral failure>.
- [ ] Implement the minimum change in <owning module>.
- [ ] Run <exact command>; confirm green; refactor and recheck if needed.
- [ ] Update product/technical specs and codemap when structure changes.
## Verification and handoff
Record red/green results, suite results and deployment/visual gaps.
```

Do not leave outline placeholders in an active design or plan. Before handoff,
review documents for contradictions, stale status, missing criteria and broken links.
