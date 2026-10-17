# Project Workflow Implementation Plan

> For agentic workers: use `superpowers:executing-plans` for future execution of
> this plan. The owner requested setup in the current checkout; keep execution inline.

**Goal:** Establish owner and agent specifications, a maintained codemap, test-first
implementation rules and authenticated Context7 research.

**Architecture:** Repository Markdown carries durable project context. Context7
configuration and its credential live in the user's Codex configuration.

**Tech stack:** Markdown, existing Python/Node tooling, Context7 CLI and hosted MCP.

**Spec:** [Project workflow design](../specs/2026-10-08-project-workflow-design.md).

## Constraints and review focus

- Preserve product behavior, existing plans and deployment evidence.
- Keep credentials outside version control and redact setup output.
- Ground baselines in code and distinguish implemented behavior from GPU proof.
- Record library freshness separately from the project's installed/pinned versions.
- Include all maintained files in the codemap, including files added by this setup.
- Documentation and configuration checks are not a production red/green test cycle.

## Task 1: Establish durable project context

**Files:** Create `AGENTS.md`, `codemap.md`, `docs/product-spec.md`,
`docs/superpowers/README.md`, and the technical baseline spec. Update `README.md`.

- [x] Inspect project source, README, package constraints, previous plans and qualification.
- [x] Write this workflow's design and plan before creating its final agent rules.
- [x] Write the living product spec with stable requirement IDs and honest statuses.
- [x] Write the technical baseline, linking requirements to modules and existing tests.
- [x] Write the spec index and reusable outlines for new designs and plans.
- [x] Add mandatory read/update, Context7 and red/green rules to `AGENTS.md`.
- [x] Build `codemap.md` from the real source inventory and add navigation guidance.
- [x] Link the documents from README; verify links, complete inventory and diff hygiene.

## Task 2: Install and verify Context7

**Files:** User-level Codex configuration, rules and installed Context7 skill;
update this design/plan with actual results. No repository credential file.

- [x] Read current official setup documentation and inspect `ctx7@latest setup --help`.
- [x] Run requested setup for Codex MCP with the supplied key and redacted output.
- [x] Inspect installed server configuration and rule/skill without printing secrets.
- [x] Verify MCP initialization, library resolution and a documentation query.
- [x] Confirm tracked changes contain no API key; report session reload requirements.

## Task 3: Document image-to-video prompt assistance

**Files:** Update `AGENTS.md`, `codemap.md`, `docs/product-spec.md`, this plan and
the [workflow design](../specs/2026-10-08-project-workflow-design.md).

- [x] Add the inspect-first, adaptive-interview and exact three-block prompt-output
  contract for image-to-video prompt assistance.
- [x] Record the official LTX image-to-video guidance lookup and preserve the
  project's stationary-camera and six-second-loop constraints.
- [x] Verify Markdown links, the maintained-file inventory, the documented review
  scenarios and `git diff --check`; record actual results below.

## Completion evidence

Context7 CLI 0.5.14 setup returned exit 0 and configured the hosted Codex MCP server,
user-level rule and `context7-mcp` skill on 2026-10-08.
Authenticated MCP initialization returned server 4.2.0. Library resolution selected
the official `/upstash/context7` ID; `query-docs` returned official Codex/API-key setup
documentation. Native tools need a new session; HTTP MCP checks succeeded here.
Codemap inventory verification covered all 101 maintained files. Local links and
trailing whitespace checks passed for all eight changed/new documents. No maintained
repository file contains the Context7 API key. Codex TOML parsed and endpoint/auth
checks passed; `git diff --check` passed. Only Markdown was changed in the project.
Product suites were not rerun; no production red/green cycle is claimed for this setup.

## Image-to-video prompt assistance evidence, 2026-10-17

Context7 resolved official LTX documentation as `/websites/ltx_io` and its
image-to-video guidance was checked on 2026-10-17. A focused contract check found
all 20 required prompt-rule phrases in `AGENTS.md`, including the listed
hair-only, clothing-only, background-only, stationary-background, no-character,
complete-instruction, inaccessible-image and conflicting-direction scenarios.
Local Markdown links in all five changed files resolved; the maintained-file
inventory contained 119 files with no additions, deletions or moves; and
`git diff --check` returned exit 0. This task changes only agent and workflow
documentation; it does not add product code or a production red/green test cycle.
