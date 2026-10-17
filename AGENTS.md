# Working on Comfy LTX Loop

## Read first

1. Read `codemap.md` before searching for code or deciding which module owns a change.
   Use its routes, then `rg` for focused searches; confirm the actual source before editing.
2. Read `docs/product-spec.md` for product intent and acceptance criteria.
3. Read `docs/superpowers/README.md`, then the relevant technical spec and plan.
4. Read `docs/qualification.md` before making deployment, GPU or visual-quality claims.

The owner's direct instructions take precedence. Preserve unrelated working-tree changes.

## Specifications are required on every implementation

- Use Superpowers: `using-superpowers` and `brainstorming` to understand the work;
  `writing-plans` for multi-step work; `executing-plans` or the explicitly chosen
  execution workflow; `test-driven-development` and `verification-before-completion`.
- Ask missing-requirement questions through Superpowers brainstorming, one focused
  question at a time, using the available user-input tool. Carry forward answers and
  existing authorization; do not ask the owner to authorize the same action again.
- Before implementing a feature, bug fix, refactor or compatibility change, update
  `docs/product-spec.md` and write/update the relevant design under
  `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.
- The product spec is for the owner: explain purpose, user-visible behavior, acceptance
  criteria and status in plain language. Technical specs are for implementation:
  identify contracts, affected modules, edge cases, compatibility, research and tests.
- Small changes may update an existing design. They still need explicit scope and
  acceptance criteria. For a refactor, state which product behavior must be preserved.
- Link stable product requirement IDs in the technical spec. Link the design from
  its plan under `docs/superpowers/plans/YYYY-MM-DD-<topic>.md`.
- Update both specs and plan during implementation when decisions or scope change,
  and before completion with delivered behavior, actual checks and remaining gaps.
  A documentation-only change updates its relevant workflow spec and product delivery
  notes; do not invent a product feature to justify it.
- Keep current specs concise. Older plans and reports provide history; unchecked old
  plan boxes are not authoritative proof that current code is missing a feature.

## Image-to-video prompt assistance

Apply these rules when a user supplies an image or accessible image path and asks
for help writing an animation prompt. This is prompt authoring only: do not change
code or specifications, prepare points, or render unless the user separately asks.

### Inspect and interview

- Inspect the image before suggesting motion. If it cannot be inspected, ask for an
  accessible image rather than inventing visual details.
- Ask questions in the user's language; write the finished prompts in English.
- Ask one focused question at a time. Remember answers and do not repeat questions
  that the user has already answered.
- Begin with the character: visible hair, then clothing/accessories, then face and
  body. Skip an absent or irrelevant category. For every part selected to move,
  clarify motion, direction, speed and amplitude as needed, offering concrete
  suggestions grounded in the inspected image.
- If no character is visible, skip character questions and begin with the visible
  background objects.
- Do not add motion the user did not request, including blinking, breathing, hair
  sway, clothing movement or expression changes.
- After character questions, ask which visible background objects should move and
  how. Identify attached structures and nearby objects that must remain stationary.
- Keep the camera stationary by default. If requested camera movement conflicts with
  this project's rendering workflow, explain that constraint before finalizing.
- Use the existing six-second loop duration unless the user specifies another. Ask
  the user to resolve conflicting motion or duration instructions before producing
  prompts, including conflicting motion directions.

### Finished prompt format

Return exactly three labelled, separately copyable fenced blocks and no additional
prompt blocks:

1. **Positive Prompt** for `motion_prompt`: approved character motion, relevant
   stationary parts and a fixed camera.
2. **Negative Prompt** for `Prompt (negative)`: concise unwanted artifacts and
   motions relevant to the user's choices.
3. **Background Prompt** for `background_prompt`: approved scenery motion and
   stationary environmental anchors.

When the background must stay still, leave the Background Prompt block empty. Do
not put `static background`, `none`, or explanatory text inside it: any nonblank
text enables background animation. For background-only animation, keep the
character stationary in Positive Prompt and put scenery motion only in Background
Prompt.

### LTX prompt writing

- Use concise, natural English with present-tense action verbs in a coherent
  single-shot description. Describe what changes over time rather than repeating
  the source image's appearance, following the official
  [LTX image-to-video guidance](https://docs.ltx.io/open-source-model/usage-guides/image-to-video).
- Name moving and stationary parts precisely: for example, moving hair tips with
  stationary roots, or moving leaves with stationary trunks. Keep wind direction
  and intensity consistent across character and scenery.
- For loops, describe smooth recurring motion returning toward the starting
  configuration. Do not promise a seamless result or introduce ping-pong playback.
- Preserve the source illustration's style. Do not add `anime`, `animation`, or
  `cartoon` to Negative Prompt merely because generic examples include them.
- Treat prompts as guidance, not guaranteed pixel protection or exact point
  trajectories.

## Test first, then production code

- For every new or changed production behavior, write a meaningful acceptance or
  regression test **before** implementation. Run it and observe the expected failure
  caused by the missing/wrong behavior. An environment error is not red evidence.
- Implement the smallest change that makes that test green. Run it again. Refactor
  only after green, then rerun affected checks. Never weaken a test to hide a failure.
- Use existing `unittest` and Node test runners; avoid introducing a testing framework
  unless the task requires it. Test contracts and outcomes rather than source strings.
- For refactors, run existing characterization tests before edits; introduce missing
  behavior coverage before restructuring. Preserve contracts rather than fabricating
  a failing test for behavior that already works.
- Record red/green commands and outcomes in the implementation plan. Before claiming
  a code change is complete, run the relevant suites and report any failures.
- Documentation-only work uses link, inventory and diff checks. Tool configuration
  uses configuration and connection checks. Do not label these checks production TDD.

Project suites (PowerShell):

```powershell
python -m unittest discover -s tests -v
$nodeTests = @(rg --files tests -g '*.mjs')
node --test $nodeTests
git diff --check
```

The editor fixture is `python tests/editor_harness.py`. A simulated queue or CPU
test does not qualify installed ComfyUI conversion, GPU inference or visual quality.

## Current library research with Context7

- Use **Context7 MCP** whenever a task asks about a library, framework, SDK, API,
  CLI tool or cloud service: syntax, configuration, setup, migrations and library-specific
  debugging. Prefer Context7 over web search for library documentation, even for familiar APIs.
- During feature planning, inspect project pins and deployment revisions, then check
  relevant current documentation through Context7 before selecting a library or API.
  Recheck changed assumptions during implementation.
- Start with `resolve-library-id`, supplying the official name and a specific research
  question, unless the owner supplies an exact `/org/project` or versioned ID.
- Select by name/relevance, official source reputation, coverage and benchmark score.
  Use version-specific IDs when available; retry a poorly matched search with a better name.
- Call `query-docs` with the selected ID and one focused concept. Use separate calls
  for independent questions; combine only when investigating their interaction.
- Record lookup date, project version/pin, documentation version/library ID, source
  links and compatibility decision in the technical spec. Context7 search results alone
  do not prove the latest release: check official release notes or package registries
  when release freshness matters. Do not upgrade dependencies merely because newer ones exist.
- If Context7 has no coverage or is unavailable, state that explicitly and use official
  documentation/releases as the fallback. Never claim a lookup that did not happen.
- Pure business-logic debugging, refactoring, code review and general programming
  concepts do not need Context7 unless the work also depends on a library contract.
- Credentials belong in user configuration/environment, never source, specs or logs.
  Context7 is configured globally for Codex; start a new session if its tools are missing.

## Maintain the codemap

- `codemap.md` stores the complete maintained project structure and module responsibilities.
- Update it in the same change whenever files/directories are added, deleted, renamed
  or moved, or when a module's responsibility changes. Include specs, plans and test files.
- Document generated/ignored/runtime directories as categories; do not enumerate changing
  output files, dependency caches, model weights or `.git` internals.
- Reconcile the map with `rg --files --hidden -g '!.git/**'` using its listed exclusions.
  Fix stale navigation before relying on it; the real filesystem is authoritative.

## Product and verification boundaries

- Primary journey: ComfyUI Load image → Prepare → edit/review → Render → preview
  → optional Upscale → save silent MP4. Keep the existing CLI compatible.
- Preserve isolated stages, explicit point review, original aspect ratio, persistent
  candidates and their timing. Do not automatically use ping-pong playback.
- Keep the official LTX baseline unchanged. Record model/ComfyUI revisions when relevant.
- Report local tests, fixture checks, deployed checks and visual acceptance separately.
  GPU and anime quality qualification remains pending until actual evidence exists.
- Before handoff, reconcile acceptance criteria, update specs/plan/codemap, inspect the
  diff and state checks and material limitations. Do not commit, push or deploy merely
  to satisfy a skill's generic workflow when the owner has not requested that operation.
