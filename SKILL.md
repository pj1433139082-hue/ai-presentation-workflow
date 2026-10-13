---
name: ai-presentation-workflow
description: Create, redesign, or resume presentation concepts, requested visual assets, or an automatically assembled editable PPTX, with a reviewable path from sources and concepts to the selected deliverable. Routes local showcases separately from strict production and component-first projects.
---

# AI Presentation Workflow

Use this skill when the task is to plan, create, redesign, or resume a presentation. The AI Presentation Workflow (APW) keeps content truth, design evidence, requested editability, and review authority connected to the selected deliverable; PPTX assembly is included only when the project selects that mode. A technically valid deck is not automatically visually accepted.

## Select the route

First inspect the brief and supplied material. Establish the audience, intended use, factual sources, delivery form, editability needs, and whether the user authorized a local draft, a formal production deliverable, or a component library.

- **Local design showcase:** Use `project-kind.json` with `contract_version: showcase-v1` and `purpose: showcase` only for an explicitly scoped, reversible local showcase. This declares the project route; it does not itself grant permission, represent user acceptance, or authorize publication. Read [references/showcase-workflow.md](references/showcase-workflow.md).
- **Ordinary deck or existing APW project:** Keep its current production contract and approved style decisions. Do not silently convert it into a showcase to avoid applicable checks. Use only the existing local-draft options when their explicit authorization and contract conditions are met.
- **Hybrid editable deck:** When a slide mixes editable copy/data with visual assets, read [references/hybrid-object-design.md](references/hybrid-object-design.md). This object strategy can be used within a showcase or a separately authorized production contract.
- **Component-first project:** Keep the existing route when the user wants each visual element delivered as independently movable/recombinable transparent components. Read [references/component-pipeline.md](references/component-pipeline.md) and its linked contracts.
- **Formal or high-stakes production:** Keep the existing strict G1–G5, decomposition, QA, and release contracts. Route to [references/stage-contracts.md](references/stage-contracts.md), [references/human-gates.md](references/human-gates.md), [references/assembly-routing.md](references/assembly-routing.md), and [references/qa-rubric.md](references/qa-rubric.md) as needed. Do not silently reclassify an existing project as `showcase-v1`.

If the requested route or required editability is unclear and materially changes the output, ask only for that missing decision. Do not ask users to approve individual objects or repair steps unless the project contract or a consequential decision requires it.

## Select the local showcase delivery mode

For a new local showcase, use the least extensive deliverable that satisfies the request. The default is **concept only**. Moving to asset production or automatic assembly requires the user to request that deliverable; concept exploration itself must not be constrained by the future PPTX object model, transparent cutouts, exact component boundaries, or assembly layout.

1. **`concept` — complete concepts only (default):** study the brief and references, then deliver contentful page concepts with source/reference lineage. This mode is complete at the concept handoff. Do not force cutout generation, object maps, PPTX assembly, or assembly review.
2. **`assets` — concepts plus requested independent assets:** deliver the concepts and the separately movable visual assets requested for reuse. If the user asks to reconstruct the whole page from blank, select `brief.delivery.asset_scope: full-slide` and read [full-slide-reconstruction.md](references/full-slide-reconstruction.md): inventory background, connectors, arrowheads, ordinary copy, special glyph art and residual details, then render from independent sources to check coverage. Background plates may be opaque; only promised cutouts require alpha. This mode ends at the asset handoff; it does not imply completed PPTX assembly or require the legacy component-first approval sequence unless that project separately selected that route.
3. **`assembly` — concepts, transparent assets, and automatic assembly:** create the requested assets, map meaningful content to tested native PPTX objects or picture objects, and assemble the deck. Review the current saved and reopened PPTX, actual renders, edit operations, and visual quality. This mode is opt-in; technical and agent checks never substitute for user visual acceptance.

In `assembly`, use the selected concept as the visual baseline. Preserve its composition, proportions, hierarchy, typography, and material choices where possible; do not impose a uniform card template or force a rearrangement to make native objects easier to assemble. Compare each current PPTX render side by side with its concept. Record visible regression as a visual miss; technical success does not count as visual success. The concept and requested assets remain valid handoffs at their own mode boundaries. This comparison does not add a human approval gate to other modes.

The local showcase CLI implements these modes. `python scripts/apw.py init ROOT` defaults to `concept`; `--mode assets` and `--mode assembly` explicitly select the other endpoints. The selection is stored in `delivery-mode.json`. `status` reports the selected completion point; `check ROOT --stage concept|assets` validates those stages; `build` is assembly-only; and `export` packages or verifies the selected endpoint. Concept/assets builds stop at the mode boundary. Existing showcase projects without `delivery-mode.json` keep legacy assembly behavior and are not silently migrated. See the [three-mode examples](examples/showcase/modes/index.html) and [apw.py entry point](scripts/apw.py); inspect its `--help` output for the current command syntax.

## Preserve the evidence chain

For every route, keep the applicable relationships inspectable. All modes preserve the brief, factual sources, reference observations, and concept lineage. Continue along the branch selected by the requested deliverable:

```text
concept:  brief and sources → reference study → complete contentful concepts → concept handoff
assets:   brief and sources → reference study → complete contentful concepts → requested transparent assets → asset handoff
assembly: brief and sources → reference study → complete contentful concepts → requested assets/object map → current PPTX → actual renders → technical and visual review
```

A contentful concept uses the slide's current copy, source-backed values or visible example labels, and real visual structure. A full-page concept image is valid as a design artifact; it is not a promise that its pixels are editable or that it can be mechanically reproduced by PPTX assembly. A final PPTX screenshot cannot be relabeled as a prior concept. In every mode, distinguish a single-page style exploration from a complete presentation. For a complete set, first establish the story and planned pages, then create and review a concept for every planned page. Declare their ordered IDs in `brief.delivery.expected_slide_ids`; the showcase check compares that optional declaration with the deck. This verifies declared coverage, not narrative quality or user acceptance. In `assembly` mode, each assembled slide needs its own prior concept; a representative pilot does not stand in for the other pages. Choose page count and representative roles from the brief, not a global five-page or three-page template.

Record enough version and hash links to identify which references and concepts produced each page, which objects were assembled, and which PPTX/render was reviewed. A changed artifact invalidates only the checks and feedback bound to that artifact or dependent scope.

Before a portable handoff, place the actual per-page prompts and generation records inside the project evidence tree and bind their local paths and hashes. Work-directory links such as `../design/` do not travel with a project-only export. Inspect the exported package and reader links as well as the source project; verify that every promised page, prompt, and record is present in the actual download.

Keep scientific, medical, and other truth-sensitive content source-grounded. Clearly distinguish source data, calculations, hypotheses, and fictional examples. Do not use generated art to alter, recreate as evidence, or supply missing factual content for a source figure, equation, result, or chart.

## Keep route-specific authority honest

For an explicitly authorized local showcase, the main agent may choose a design direction when that choice is within the recorded task scope. Record the actual actor as `agent chosen` with the selected reference/concept lineage; do not convert it into a human approval. This permission belongs to that task and must not be assumed for future projects. Formal brand, factual, regulated, or external-release decisions stay with the authorized human decision-maker.

In `assembly` mode, inspect the actual assembled PPTX render. Record machine-verifiable technical results, agent visual inspection, and user feedback separately. An agent may report `agent-reviewed draft`; record user visual acceptance only when the user actually saw and explicitly accepted that exact version and scope. No machine check, multiple-agent agreement, project kind, export, or silence supplies that decision.

Use the current `scripts/apw.py --help` and subcommand help when command versions may differ. Treat native-object support the same way: verify each promised operation against the current backend and saved PPTX. Do not claim a command, object type, render, export, or validation passed until it runs against current files. This workflow does not prevent agents from generating files outside APW, and it does not certify those files as APW-complete.

## Use the image-generation route

When image generation or editing is needed, use the `imagegen` skill and Codex built-in `image_gen`. In `concept` mode, a full-slide generated image may be the concept deliverable. In `assets` or `assembly` mode, generate requested transparent visual assets as separate components where useful. Never use a full-slide concept image as the flattened final PPTX when the user expects editable content. Keep the prompt, source references, generated output, and revision lineage with the project.

Use reference-guided local prompt edits for targeted concept repairs, clean background plates, isolated objects and occlusion repairs. Inspect the actual edit target first; state the target change and surrounding preservation requirements, retain every attempt, then compare both edited and untouched areas. This is generative reconstruction, not guaranteed pixel-preserving extraction. Short special typography can be isolated glyph art; a raster concept does not yield a recoverable font file. See [full-slide-reconstruction.md](references/full-slide-reconstruction.md).

For style exploration, start with the content and intended viewing format. Give parallel designers freedom over composition, typography, palette, materials, and visual metaphor. Read the selected examples' original prompts and view their images; record how their principles transfer. Do not impose final assembly constraints on exploratory concepts. Review the resulting alternatives before defining the selected project's readability and editability parameters.

## Load only the active references

- Competition, innovation-project defense, or student entrepreneurship pitch: read [references/competition-presentations.md](references/competition-presentations.md). Select the story from the project stage, work category, and applicable event brief; keep the requested delivery mode and full-page concept coverage.
- Showcase lifecycle and review semantics: [references/showcase-workflow.md](references/showcase-workflow.md).
- Native text/shape/table/chart and image-object choices: [references/hybrid-object-design.md](references/hybrid-object-design.md).
- Story and speaker notes: [references/narrative-and-speaker-notes.md](references/narrative-and-speaker-notes.md); source finding and truth-sensitive research: [references/research-routing.md](references/research-routing.md).
- Existing reference-board and richness process: [references/reference-first-design.md](references/reference-first-design.md); personal style reuse: [references/reusable-style-library.md](references/reusable-style-library.md). These are not mandatory reference counts for `showcase-v1`.
- Project readability parameters and cross-slide meaning: [references/readability-contract.md](references/readability-contract.md) and [references/semantic-visual-grammar.md](references/semantic-visual-grammar.md), when relevant to the selected profile or brand system.
- Strict/component-first projects: load the active-stage [references/stage-contracts.md](references/stage-contracts.md) plus relevant [references/human-gates.md](references/human-gates.md), [references/component-pipeline.md](references/component-pipeline.md), [references/page-parallel-production.md](references/page-parallel-production.md), [references/prompt-patterns.md](references/prompt-patterns.md), [references/visual-providers.md](references/visual-providers.md), [references/assembly-routing.md](references/assembly-routing.md), [references/local-agent-qa.md](references/local-agent-qa.md), [references/qa-rubric.md](references/qa-rubric.md), and [references/visual-qa-tolerance.md](references/visual-qa-tolerance.md). Load only what the active stage needs.

Do not load the complete legacy production packet for a `showcase-v1` task unless a specific risk or user requirement makes that contract relevant. Conversely, a local draft preference does not weaken a formal production contract or authorize G5 release.

## Preserve the legacy PPTX handoff

When the selected deliverable is an assembled PPTX, retain its verified three-folder handoff: `确定概念图/`, `组件/`, and `PPT成稿/`. The showcase exporter uses the same folder names but records native objects in `PPT成稿/项目证据/`; they are not PNG components. Use `apw.py export` and its `--verify` for the selected route only after verifying current support; the existing `export_final_package.py` also dispatches explicit showcase projects. Report technical checks, agent review, user feedback, and formal G5 separately. Concept-only and asset-only requests are complete at their selected handoff and must not be described as completed PPTX projects.
