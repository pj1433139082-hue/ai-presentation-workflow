---
name: ai-presentation-workflow
description: Use when creating or redesigning a PPT/PPTX from a brief or reference, when full-slide images must become reusable transparent components, when table/chart text and data must stay editable, or when presentation stages repeatedly stall because inputs, outputs, approvals, research evidence, or QA are unclear.
---

# AI Presentation Workflow

Build a deck as a resumable production system. The canonical deliverable is a transparent component library plus placement metadata; PPTX assembly is optional. A full-slide concept is a visual contract, never a final flattened background.

The first complete full-slide deliverable after the approved story and style calibration is a contentful review concept: it shows the approved title, concise on-slide copy, truth/status labels, and representative imagery. G4 approves these versioned review images and their copy/source record. Only after that approval may the workflow derive a textless component master, then inventory and split its visuals into transparent components.

## Start

1. Announce this skill and the current stage. Resume from `run-state.json`; never overwrite approved work.
2. Copy `assets/project-template/` for a new run. Probe research, image, assembly, rendering, and validation capabilities at runtime.
3. Before asking the user anything, inspect every supplied file and record its hash plus extracted facts in `alignment.json`. Never ask for a fact that is already available in the material.
4. Build the current question frontier from unresolved consequential decisions. Ask 3–5 independent questions per round when that many are available; give a recommended answer and impact for every question. Hold dependent questions for the next round.
5. Load only the active-stage reference:
   - contracts/state: `references/stage-contracts.md`
   - human decisions: `references/human-gates.md`
   - research: `references/research-routing.md`
   - reference study and production richness: `references/reference-first-design.md`
   - readable text and image display regions: `references/readability-contract.md`
   - decomposition: `references/component-pipeline.md`
   - prompts: `references/prompt-patterns.md`
   - visual provider routing/adapters: `references/visual-providers.md`
   - assembly: `references/assembly-routing.md`
   - QA/repair: `references/qa-rubric.md`

**REQUIRED SUB-SKILL:** Use `imagegen` for image work and Codex built-in `image_gen`; do not silently substitute another service.

## Production route

Default to `full-tracked`. For high-stakes, multi-session, research-heavy, or still-ambiguous work, use `grill-with-docs → to-spec → to-tickets → implement` when those skills are installed, then execute the stage machine below.

Use `fast` only after G1 proves that every consequential decision is already approved, the work is not high-stakes, and it will not require multi-session coordination. Record the exact separate confirmation `确认快速路线` in `run-state.json`. Fast may skip the external Spec and Tickets planning artifacts and proceed to implementation, but it never skips source inspection, project stage artifacts, validation, or G1–G5. If eligibility changes, switch to `full-tracked`.

## Invariants

- Ordinary titles, body copy, labels, numbers, and user data are final-slide `fill_slots`, never baked into generated component art; the contentful review image is a temporary visual exception, not an editable deliverable.
- Every visual item is its own transparent PNG, including arrows, basic shapes, panels, table/chart shells, and approved special typography.
- Table/chart shells contain no text or data. Remove data-encoding marks as well as values and labels.
- Special typography is opt-in: lock `exact_text`, verify it, and require human approval.
- Preserve truth-sensitive screenshots, figures, equations, and plots unchanged or blank their variable content; never redraw facts generatively without approval.
- Generate one distinct asset per call. Reuse approved repeated assets.
- Never place the concept render behind editable text and call the result editable.
- Full-slide review concepts may show ordinary copy for human review; final textless masters and generated components may not contain it. Treat the contentful image as review-only.
- Give every contentful revision a new versioned path and keep prior images as history. G4 approval binds the exact image, copy/source log, and review contact sheet.
- Do not generate a textless master or start inventory before current G4 approval. Record each master against the approved contentful hash and preserve every fill-slot coordinate. Before inventory, save a 100%-scale side-by-side human geometry review of the contentful image and textless master, bound to both image hashes.
- Manifest every prompt, reference, output, hash, alpha check, status, and approval.
- Component extraction prompts are adapter-derived from approved references, crops, and roles; never append caller-written free-form prompt text.
- Route visual skills only through `visual-provider-registry.json` and a compatible PPT adapter. Provider-native full-page output never bypasses the component, truth, text, or approval contracts.
- Keep exactly one `primary_visual_family`. Secondary providers require declared page roles. Photo routes require a hash-verified human source-rights record; strong-style providers require explicit opt-in plus a hash-locked G4 special-page approval. Social Card requires a G5-approved deck hash and a separately human-approved derivative brief; it is a derivative, never a slide renderer.
- Default real work to `quality_profile: production`. `validation-fixture` is only for contract/tool tests, requires `fixture_only: true`, and is never evidence of production visual quality.
- Before the first production concept, curate and analyze a 3–6 image reference board. Pass selected project-local reference images plus their transferable rules and do-not-copy boundaries to `image_gen`; a gallery ID or style adjective alone is insufficient.
- Before the three anchors, generate 2–3 actual same-content calibration concepts, varying visible direction, visual strength, or layout density. Show them to the user and record a hash-bound selection; do not infer a preference from a reference board or expand the deck while calibration is pending.
- Production richness comes from information structure, visual layers, and layout variation. Ordinary content slides must meet the approved `composition_profile`; do not repeatedly emit title + short copy + one decorative object, and do not inflate counts with decorative noise.
- Plan legible text and usable main-image regions before concept generation. At G4, show the full-deck contact sheet **and every contentful slide at full size**; underfloor font or evidence-frame dimensions require a specific, approved exception. Do not solve crowding by silently shrinking copy or screenshots.

## State machine

| Stage | Output | Gate |
|---|---|---|
| Intake + research | `brief.json`, `alignment.json`, `run-state.json`, `research-bundle.json` | G1 authority/boundary |
| Story | `storyboard.json` | G2 narrative/titles |
| Style + spec | `reference-study.json`, `concept-calibration.json`, `style-contract.json`, `capability-report.json`, `deck-spec.json` | G3 reference board → same-content concept calibration and user selection → three anchors |
| Concepts | versioned contentful `concepts/<slide-id>/<version>.png`, `concept-generation-log.json` | G4 content and contact-sheet approval |
| Inventory + assets | `component-master-manifest.json`, `scene-graph.json`, `asset-manifest.json`, transparent PNGs | G4 must be current before master creation |
| Assembly + QA | `assembly-map.json`, optional PPTX, `qa-report.json` | G5 release |

Read `references/stage-contracts.md` for the full S0–S10 contract. A rejection returns only to the stage that owns the defect.

## Human boundary

Humans decide meaning, authority, brand, truth exceptions, and release: G1 brief/evidence authority; G2 story; G3 reference selection, contentful calibration, visual-strength/density calibration, richness and readability profiles, direction, and anchors; G4 the exact full-deck copy, imagery, layout, and full-size readability; G5 final package. The agent resolves searchable facts, tool syntax, retries, coordinates, and file operations. Use `references/human-gates.md` for approval packets.

G1 is a hard boundary for audience, decision goal, source authority, truth boundaries, research permission, delivery form, and editability promises. Do not enter Story while any of these decisions is missing, ambiguous, or covered only by a stale approval. G2–G4 use the same versioned approval rule for story, visual anchors, and the full concept sheet. `全部按推荐` is valid only when the complete current recommendation packet is visible and the approval is bound to the current artifact version and SHA-256 hashes. Do not treat `按推荐`, silence, or an earlier conversation as approval. G5 never inherits a prior batch approval; release requires the exact separate confirmation `确认发布`.

## Validate and recover

```bash
python scripts/validate_project.py <project-dir> --stage <stage>
```

Advance only on exit `0`. Structural validation does not replace visual QA or G5. Repair the smallest owning artifact, keep approved versions, and limit one defect class to three focused image repairs before recording a blocker.

Release only when all gates are approved, the release validator passes, every concept element maps to a component or fill slot, no ordinary text/data is baked into art, no concept is flattened into the final deck, and the assets, maps, prompts, evidence, and QA package are complete.
