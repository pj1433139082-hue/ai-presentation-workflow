# Stage contracts

## Canonical terms

- **Contentful review concept**: a versioned full-slide image containing the approved title, concise on-slide copy, visible truth-status labels, and representative imagery. It is for human review and is never a final slide background.
- **Textless component master**: the post-G4 visual master derived from an approved contentful concept after ordinary copy and data are removed; it preserves the approved composition and fill-slot geometry.
- **Transparent component**: one isolated visual layer with alpha. This includes arrows and basic shapes, not just illustrations.
- **Fill slot**: a blank reserved region for ordinary text, labels, values, or user-supplied data.
- **Scene graph**: normalized placements and z-order for every component on a slide.
- **Asset manifest**: the source of truth for component role, prompt, provenance, status, and output.
- **Special typography**: an opt-in image component containing exact decorative text. It is never a substitute for ordinary copy.
- **Truth-sensitive visual**: a screenshot, experiment result, equation, plot, or other factual image whose content must not drift.
- **Reference study**: an analyzed visual reference with observations, transferable rules, project translation, and explicit do-not-copy boundaries. A URL or gallery ID alone is not a study.
- **Concept calibration**: 2–3 real concept images for one fixed-content slide, compared before anchor generation to select direction, visual strength, and layout density.
- **Information unit**: a meaningful claim, evidence item, mechanism step, comparison dimension, decision, or action; titles and decorative labels do not count.
- **Visual layer**: a distinct communication layer such as a main visual, diagram, data shell, connector system, evidence image, or annotation layer; background decoration does not count.

## State model

Use this state sequence:

`intake → research → story → style → spec → concept → inventory → assets → assembly → qa → released`

`run-state.json` records the current state, gate decisions, artifact versions, blockers, and any rollback. Every approval contains `status`, `approver`, `approved_at`, `artifact_version`, `approval_mode`, `approval_phrase`, an approval packet, and `approved_artifacts` mapping paths to SHA-256 values. G1 keeps its packet in `alignment.json`; G2–G5 embed theirs in the gate record. The validator rejects stale hashes or a version that differs from `artifact_versions`.

It also records `production_route`. `full-tracked` is the default and requires planning artifacts; use the `grill-with-docs → to-spec → to-tickets → implement` chain when installed. `fast` is valid only with exact confirmation `确认快速路线`, current G1 approval, all consequential decisions approved, `high_stakes: false`, and `multi_session: false`. Fast skips only the external Spec/Tickets planning documents. It does not skip any project artifact, validation stage, or G1–G5 approval.

G2 packet decisions are slide sequence, action titles, slide messages, evidence mapping, and appendix boundary. G3 covers reference selection, contentful same-content concept calibration, the approved composition/richness and readability profiles, visual direction, observable style rules, and three representative contentful anchors. G4 covers `contentful_copy_source_review`, the full contentful contact sheet, per-slide full-size `readability_review`, slide-by-slide layout/richness review, blank table/chart regions, special typography, and slide deviations. G5 covers final render, concept differences, QA exceptions, component usability, and the deliverable index. G2–G4 allow explicit approval or the exact batch phrase `全部按推荐`; G5 accepts only `approval_mode: release` with `确认发布`.

`rollback` is null during normal progress. On rejection it records `trigger: rejection`, `source_gate`, `owner_stage`, and reason; the rejected gate clears its prior approval epoch before it can advance again. On QA failure it records `trigger: qa-defect`, `defect_class`, `owner_stage`, and reason. Every rejected gate requires the matching rollback record. The owner mapping is deterministic: research, story, style, concept, inventory, assets, assembly, or QA. Only the owning stage is reopened; unrelated earlier approvals remain unless their artifacts change.

## Artifact contracts

### `brief.json`

Required:

- `project_id`
- `audience`
- `goal`: the decision or change the deck should produce
- `delivery.formats`: any of `component-library`, `pptx`, `pdf`, `contact-sheet`
- `delivery.aspect_ratio`
- `editability`: distinguish `native-editable`, `component-editable`, and fixed evidence; explicitly state whether internal vector paths must be editable
- `capacity_budget`: component limit, generation-call limit, retry limit, deadline, and fallback delivery
- `quality_profile`: `production`, `draft`, or `validation-fixture`; real deliverables default to `production`

Recommended: `slide_count_range`, `language`, `deadline`, `brand_constraints`, `source_authority`, `truth_sensitive_items`, `must_include`, `must_avoid`, `assembly_preference`.

### `alignment.json`

This is the G1 decision ledger. It records:

- `material_review`: whether material was supplied, which files were inspected, their SHA-256 hashes, and inspection notes
- `discovered_facts`: stable fact ID, the decision it informs, its value, and source references
- `decisions`: the seven critical G1 decisions plus any non-blocking mechanics; each record has status, value, basis, and an optional recommendation
- `question_frontier`: at most five currently independent unresolved decision IDs
- `approval_packet`: G1, current artifact version, covered decision IDs, and whether recommendations were visible

The seven critical IDs are `audience`, `decision_goal`, `source_authority`, `truth_boundaries`, `research_permission`, `delivery_form`, and `editability_commitment`. All must have meaningful non-empty values before Story. Questions on the frontier require a recommended value, reason, impact, and `independent: true`. Ledger order is priority order: the frontier is the first five available independent decisions, or all available decisions when fewer than five remain; if three or more are available, at least three must be asked. A discovered fact cannot remain on the frontier. Extra low-risk mechanics may remain open without blocking Story.

For batch approval, every critical decision must accept the visible recommended value, `approval_mode` is `batch-recommendations`, and the exact phrase is `全部按推荐`. Individual confirmation uses `approval_mode: explicit` plus `decision_approvals`, whose per-decision value hashes must match the current ledger. Recommendation shortcuts are invalid in explicit mode. Both modes are invalidated by a changed artifact hash or version.

### `research-bundle.json`

Set `mode` to `external`, `source-only`, or `not-required`. `not-required` needs a reason; it is valid when approved supplied sources are sufficient and external research is forbidden or unnecessary.

Artifact arrays:

- `query_log`: query, engine/tool, date, filters, result/error state
- `sources`: stable ID, original URL/path, title, publisher, date, source kind, access date
- `claims`: claim ID, concise claim, supporting source IDs, confidence, intended slides
- `gaps`: unanswered questions and their impact
- `assumptions`: explicit, testable assumptions
- `rejected_sources`: source plus rejection reason

Search snippets are discovery aids, not evidence. Claims cite opened original sources.

### `storyboard.json`

Each slide requires:

- stable `id` such as `S01`
- action-oriented `title`
- one-sentence `message`
- `narrative_role`: opening, context, tension, evidence, mechanism, proposal, decision, next-step, appendix
- `evidence_ids`
- `evidence_policy`: `required` or `not-applicable`; the latter needs `evidence_not_required_reason`
- `visual_intent`

The title-only test should reproduce the story when titles are read in order.

### `reference-study.json`

Read `references/reference-first-design.md` before creating this artifact. A production study requires:

- `version`, `status: analyzed`, and `reference_contact_sheet` with a project-local path and SHA-256;
- 3–6 `references`, each with stable ID, source kind and locator, project-local image path/hash, rights/usage note, `status: analyzed`, structured observations, transferable rules, project translation, do-not-copy boundaries, and target slide roles;
- 2–3 `direction_options`, each citing known reference IDs and stating structure, palette, density, imagery, and tradeoffs;
- `recommended_direction_id` and `selected_reference_ids`.

Selected reference images are passed to `image_gen` for production concepts. Use them for design grammar only. Do not copy protected copy, logos, characters, or a distinctive finished composition.

`validation-fixture` may use `status: not-required` with a reason. It must not be presented as a production reference study.

### `concept-calibration.json`

For production/draft, record `version`, `status: generated`, one storyboard `slide_id`, and `fixed_content` copied exactly from that slide (`title`, `message`, `evidence_ids`, `visual_intent`). Calibration images show that exact title and message plus representative imagery. Store shared `copy_map` and `source_lineage` records; each variant records its image classification and a hash-bound human-checked text transcript. Keep any remaining editable regions in `fixed_fill_slots`. Record a `contact_sheet` path/hash and 2–3 `variants`. Each variant has a stable ID, known `direction_id`, `style_strength`, `layout_density`, exact prompt, Codex `image_gen` tool/model, generation time, attached reference IDs/paths/hashes, and output path/hash. The candidates must differ in at least one of direction, strength, or density. Record `recommended_variant_id` plus recommendation reason and impact. The G3 `calibration_selection` approval binds this artifact, source files, transcript evidence, comparison sheet, and all images by SHA-256 before anchors are generated. Fixture-only runs may use `status: not-required` with a reason.

### `style-contract.json`

Record:

- selected direction and rejected alternatives
- selected calibration variant ID, selected direction ID, visual strength, and layout density; these must match the human-selected candidate
- palette, typography intent, spacing rhythm, shape language, image treatment, density
- selected reference IDs that match `reference-study.json`
- `concept_reference_mode`; production uses `image-and-analysis`
- `pass_selected_images_to_image_gen`; production requires `true`
- `composition_profile`: quality profile, visual richness, minimum layout-archetype count, maximum consecutive repeated archetypes, minimum information units and visual layers for ordinary content slides, and allowed sparse narrative roles
- `readability_profile`: minimum action-title/body/caption/source font sizes and usable main evidence, fine-UI, and illustration area floors; see `references/readability-contract.md`
- any `awesome-gpt-image-2` category/template/case IDs used
- invariants and prohibited motifs
- exactly three `anchor_concepts`: opening, typical, and highest-risk, each with slide ID and file path

Do not store a pile of adjectives. Translate taste into observable rules.

### `capability-report.json`

Record time-stamped probes for research, Codex `image_gen`, real transparent PNG output, assembly backend, and render/inspection. Before S7, generate a small test asset and validate the file itself has PNG alpha; a prompt that merely asks for transparency is not proof. If PPTX is requested, verify one assembly backend and use only that backend for the run.

### `concept-generation-log.json`

For every production contentful concept, record the slide ID and immutable version, exact prompt, `codex-image_gen` tool/model identity when available, selected calibration variant ID, visual strength, layout density, every attached reference ID/path/SHA-256, output path/SHA-256, and status. `copy_map` records every visible word and exact title/message mappings to the approved storyboard. Other copy cites a source quote or an explicit paraphrase for G4 review. `source_lineage` accepts any user-authoritative source format plus the approved storyboard or brief; each source has a project-local path, SHA-256, approved/verified status, and locator. `image_inventory` classifies representative imagery as `illustrative`, `verified-source`, or `pending-placeholder`; illustrations are labeled and never used as evidence, while factual images link to unchanged, hash-verified sources. `text_review` records observed text per copy ID and a transcript artifact/hash. If deterministic overlays repair glyphs, retain the prior image and record input/output hashes and overlay evidence. The validator checks records and hashes; metadata or OCR alone is not proof that an image is correct. G4 binds the log, transcript evidence, source files, contact sheet, and every contentful image. The output must match its `concept_path`.

### `deck-spec.json`

At the root, add `production_estimate` with unique component count, planned generation calls, reserved retries, and estimated completion when a deadline exists. At inventory/release, reconcile it with manifest asset count and each generated asset's `generation_attempts`.

Each slide requires:

- `id`, `title`, `message`
- `concept_path` after S5, pointing to the current contentful review concept, not its textless master
- `components`: stable component IDs
- `fill_slots`: stable ID, kind, normalized `[x,y,w,h]`, intended editable content
- `composition`: layout archetype, complexity (`sparse`, `standard`, or `rich`), information units, visual layers, selected reference IDs, and variation from the previous slide
- `readability`: every ordinary text/data fill slot's planned font and line count, the usable main-visual bbox, any specific underfloor exception, and a 100%-scale review record bound to the current contentful image hash from the Concept stage
- optionally `speaker_notes`, `citations`, `transition`, `accessibility_notes`

Normalized coordinates are in the range 0..1 and must stay within the canvas.

For a production deck, ordinary content slides meet the approved composition-profile minimums. Sparse slides are limited to approved roles. When the deck has enough pages, use the approved minimum number of layout archetypes, do not exceed the consecutive-repeat limit, and include a rich content slide unless an approved restrained direction says otherwise. Counts are planning evidence, not a loophole: G4 and QA verify that units and layers are meaningful in the render.

### `scene-graph.json`

Each slide records its canvas and every visual element:

- `component_id`
- globally unique `instance_id`; repeated placements may reuse one `component_id`
- normalized `bbox: [x,y,width,height]`
- integer `z`
- optional `rotation`, `opacity`, `crop`, `blend_notes`, `reused_from`

Run two passes: semantic inventory first, residual pixel inventory second. The second pass catches decorative fragments, shadows, separators, masks, and connectors omitted by semantic labeling.

### `component-master-manifest.json`

Create this only after the current G4 approval. Record one textless master per slide with its versioned path/hash, approved contentful concept path/hash, and current approved `concept-generation-log.json` hash. Set `text_policy: textless`, `ordinary_text_removed: true`, and `contains_ordinary_text: false`. `preserved_fill_slots` must exactly match the slide's fill-slot IDs, kinds, and normalized bounding boxes in `deck-spec.json`. Add a `geometry_review` with a separate side-by-side comparison image path/hash, reviewer, 100%-scale passed status, hashes of both reviewed images, and passed composition/fill-slot/text-removal checks; it is a mandatory human check before inventory. Never use a contentful concept as a component master or final flattened slide.

### `asset-manifest.json`

Each asset requires:

- `id`, `slide_id`, `role`
- registered `provider_id`, `adapter_id`, `page_role`, `source_kind`, and component-role compatibility for provider-backed visuals
- registered `output_class`, `provider_transparency_behavior`, and `provider_aspect_ratio_behavior`
- `strategy`: normally `generated-transparent-png`; use `preserved-transparent-png` only for an unchanged source cutout
- `content_policy`
- `background_requirement: transparent`
- `prompt`, reference paths, output path
- generation tool/model identity when available
- `generation_attempts` for generated assets
- `editability`: `component-editable` for transparent PNGs, `native-editable` for approved native objects, or `fixed-evidence` for preserved factual assets
- `sha256`
- alpha metadata
- status and review evidence

Role rules:

- `table-shell` and `chart-shell`: `content_policy: blank-fill-slots`, `contains_text: false`, `contains_data: false`, and non-empty `fill_slot_ids`
- all roles except `special-typography`: no embedded ordinary text
- `special-typography`: `exact_text`, language, OCR result, and `human_approved`
- truth-sensitive sources: preserve unchanged or blank their variable content; record the decision

Truth-sensitive assets record `source`, `source_sha256`, output hash, and preservation strategy. Exact-preservation strategies must hash-match the source.

Allowed truth-sensitive strategies are `preserved-raster`, `preserved-vector`, and `preserved-truth-sensitive`. Masked alteration is intentionally blocked until a deterministic mask-outside pixel comparison is available. “Decomposition” normally means reference-guided per-component regeneration, not lossless pixel-layer extraction; state this limitation in G3/G4.

### `assembly-map.json`

For each slide record component IDs, fill-slot IDs, unique continuous `output_index`, optional `pptx_part`, backend, and `flattened_concept_used: false`. If PPTX is requested, also record its output path and SHA-256. Validation checks required Office package parts, XML readability, actual relationship order, expected slide count, a media whitelist bound to approved manifest assets, concept-image hashes, and near-full-slide raster pictures. The scene graph governs placement; do not tune positions only inside the PPTX without updating it.

### `qa-report.json`

Record overall status, per-slide status, checks performed, evidence files, differences from the concept, exceptions, repairs, and final reviewer. Production release requires explicit `reference-transfer`, `composition-richness`, and `readability-full-size` checks. Release also requires `final_contact_sheet`, `exception_register`, and `deliverable_index` paths. G5 approval hashes those three files plus every global and per-slide QA evidence file. For PPTX, `subject_sha256` binds QA to the assembled file. A declared exception identifies the owner, reason, and user acceptance.

## Transition ownership

- Research defects return to S1.
- Story hierarchy defects return to S2.
- Style inconsistency returns to S3 or the specific concept in S5.
- Missing/merged components return to S6.
- Alpha, crop, or isolated-asset defects return to S7.
- Placement and stacking defects return to S8.
- QA never repairs files silently; it identifies the owning stage.

The action-title and storyboard discipline is informed by [SlideSage](https://github.com/vedraut/slidesage); this skill adds explicit research evidence, human gates, and component decomposition contracts.
