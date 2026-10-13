# Stage contracts

> Scope: The S0–S10 state machine, fixed production artifacts, and G1–G5 approval contracts below describe the legacy strict-production profile. A `showcase-v1` project must not use these fields to imply formal approval; route it through [showcase-workflow.md](showcase-workflow.md).

## Canonical terms

Review and authority vocabulary is defined in `../CONTEXT.md`; the artifact terms below remain the production vocabulary.

- **Contentful review concept**: a versioned full-slide image containing the approved title, concise on-slide copy, visible truth-status labels, and representative imagery. It is for human review and is never a final slide background.
- **Textless component master**: the post-G4 visual master derived from an approved contentful concept after ordinary copy and data are removed; it preserves the approved composition and fill-slot geometry.
- **Transparent component**: one isolated visual layer with alpha. This includes arrows and basic shapes, not just illustrations.
- **Fill slot**: a blank reserved region for ordinary text, labels, values, or user-supplied data.
- **Scene graph**: normalized placements and z-order for every component on a slide.
- **Decomposition map**: the post-G4, per-slide inventory mapping each visible operable object to one scene instance or an explicitly editable fill slot, with numbered full-size review evidence and a human coverage decision. It is not an alpha check or proof of semantic isolation by itself.
- **Asset manifest**: the source of truth for component role, prompt, provenance, status, and output.
- **Special typography**: an opt-in image component containing exact decorative text. It is never a substitute for ordinary copy.
- **Truth-sensitive visual**: a screenshot, experiment result, equation, plot, or other factual image whose content must not drift.
- **Reference study**: an analyzed visual reference with observations, transferable rules, project translation, and explicit do-not-copy boundaries. A URL or gallery ID alone is not a study.
- **Concept calibration**: 2–3 real concept images for one fixed-content slide, compared before anchor generation to select direction, visual strength, and layout density.
- **Information unit**: a meaningful claim, evidence item, mechanism step, comparison dimension, decision, or action; titles and decorative labels do not count.
- **Visual layer**: a distinct communication layer such as a main visual, diagram, data shell, connector system, evidence image, or annotation layer; background decoration does not count.
- **Semantic visual system**: a G3-approved map from text and frame role IDs to one meaning and treatment each, plus repeated-region anchors. It is not a fixed brand template; see `references/semantic-visual-grammar.md`.

## State model

Use this state sequence:

`intake → research → story → style → spec → concept → inventory → pilot → assets → assembly → qa → released`

`run-state.json` records the current state, gate decisions, artifact versions, blockers, and any rollback. Never set `stage: released` while G5 is pending; that stage requires an approved release gate, even if an earlier-stage structural check passes. Every approval contains `status`, `approver`, `approved_at`, `artifact_version`, `approval_mode`, `approval_phrase`, an approval packet, and `approved_artifacts` mapping paths to SHA-256 values. G1 keeps its packet in `alignment.json`; G2–G5 embed theirs in the gate record. The validator rejects stale hashes or a version that differs from `artifact_versions`.

It also records `production_route`. `full-tracked` is the default and requires planning artifacts; use the `grill-with-docs → to-spec → to-tickets → implement` chain when installed. `fast` is valid only with exact confirmation `确认快速路线`, current G1 approval, all consequential decisions approved, `high_stakes: false`, and `multi_session: false`. Fast skips only the external Spec/Tickets planning documents. It does not skip any project artifact, validation stage, or G1–G5 approval.

G2 packet decisions are slide sequence, action titles, slide messages, evidence mapping, and appendix boundary. G3 covers reference selection, contentful same-content concept calibration, the approved composition/richness and readability profiles, visual direction, observable style rules, the semantic visual system for v2 projects, and three representative contentful anchors. G4 covers `contentful_copy_source_review`, the full contentful contact sheet, per-slide full-size `readability_review`, cross-slide semantic review for v2 projects, slide-by-slide layout/richness review, blank table/chart regions, special typography, and slide deviations. G5 covers final render, concept differences, QA exceptions, component usability, and the deliverable index. G2–G4 allow explicit approval or the exact batch phrase `全部按推荐`; authorized local mode also allows a clear current `local-affirmative` reply with all packet/decision/hash bindings. G5 accepts only `approval_mode: release` with `确认发布`.

Between G4 and asset production, `run-state.json.gates.decomposition` is a separate human gate. At `inventory`, the numbered image, readable list, scene graph, and decomposition map may be prepared and reviewed. At `pilot` or later, the gate must be approved with `approval_mode: explicit` in strict mode or a clear current `local-affirmative` reply in authorized local mode, the actual approval phrase, a current `artifact_version`, and hash-bound approved artifacts for `decomposition-map.json`, every reviewed concept and textless master, and every numbered image and readable list. Its packet decisions are `object_inventory`, `coverage_review`, and `review_evidence`; these must equal the current map. Human coverage remains required in both modes. A rejected decomposition gate clears its approval epoch and rolls back to `inventory` without changing unrelated G1–G4 approvals. Any source/list/review image change makes the old approval stale.

For production, the post-decomposition `pilot` stage is a separate batch-production gate. Select an object-rich content slide in `pilot-plan.json` (slide ID, all of its component IDs, and a selection rationale); complete only its assets, then use the actual PPTX backend to assemble and render that page. `scripts/render_pilot_review.py` emits a pending review packet: current contentful concept, every selected asset's isolation evidence, actual 1920×1080 PPTX render, 3840×1080 side-by-side, and 1920×1080 half-opacity overlay. Review single-object identity, missing items, placement, seams, color/z-order, usable text/main-image regions, and factual labels. Texture differences alone are not pixel-level failure. Strict mode needs explicit current `确认单页试拼` and `status: approved`; authorized local mode may instead record `status: agent-verified-local`, `actor: agent`, and `review_mode: agent-QA-user-authorized-continuous-local` after actual inspection. Both require a real reviewer, timezone-aware timestamp, all seven passed checks, no unresolved defects, and hashes binding the concept, selected deck/scene/decomposition records and asset records, PPTX, render, and evidence. A changed selected page or asset invalidates review; other pages can be produced afterward without invalidating it. Rejection records object/page, evidence, owner stage, and local repair entry. A changed concept needs a new version and the affected human approvals again. `--stage assets` requires this pilot gate for production; `validation-fixture` only tests the contract and cannot establish real-project visual quality.

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

For batch approval, every critical decision must accept the visible recommended value, `approval_mode` is `batch-recommendations`, and the exact phrase is `全部按推荐`. Individual confirmation uses `approval_mode: explicit` plus `decision_approvals`, whose per-decision value hashes must match the current ledger. Authorized local mode also accepts a clear `local-affirmative` reply plus the same per-decision evidence and complete current seven-decision packet. Recommendation shortcuts are invalid in explicit mode. All modes are invalidated by a changed artifact hash or version.

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

For production/draft, record `version`, `status: generated`, one storyboard `slide_id`, and `fixed_content` copied exactly from that slide (`title`, `message`, `evidence_ids`, `visual_intent`). Calibration images show the exact title plus concise, source-backed on-screen realization of the approved narrative message and representative imagery. Store shared `copy_map` and `source_lineage` records; if the message is not verbatim on-screen, store `message_mapping` with the exact `storyboard_message`, all visible message-realization `copy_ids`, a concrete semantic/truth-boundary `review_note`, and `human_gate: G3/G4-required`. This metadata is not proof of semantic equivalence; the human checks it against the actual image at G3/G4. Each variant records its image classification and a hash-bound human-checked text transcript. Keep any remaining editable regions in `fixed_fill_slots`. Record a `contact_sheet` path/hash and 2–3 `variants`. Each variant has a stable ID, known `direction_id`, `style_strength`, `layout_density`, exact prompt, Codex `image_gen` tool/model, generation time, attached reference IDs/paths/hashes, and output path/hash. The candidates must differ in at least one of direction, strength, or density. Record `recommended_variant_id` plus recommendation reason and impact. The G3 `calibration_selection` approval binds this artifact, source files, transcript evidence, comparison sheet, and all images by SHA-256 before anchors are generated. Fixture-only runs may use `status: not-required` with a reason.

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
- for new projects, `contract_schema_version: 2` and `semantic_system`: `text_roles` (meaning, readability role, exact native font family/pt/bold/color), `frame_roles` (meaning, solid/dashed/none line treatment, color and visible-label requirement), and `repeated_regions` (text role, required flag, normalized anchor and tolerance). These are project-chosen tokens, not B7 constants. Legacy projects without v2 remain valid until a versioned style amendment is approved; never edit an approved style file in place merely to satisfy a new validator.
- any `awesome-gpt-image-2` category/template/case IDs used
- invariants and prohibited motifs
- exactly three `anchor_concepts`: opening, typical, and highest-risk, each with slide ID and file path

Do not store a pile of adjectives. Translate taste into observable rules.

### `capability-report.json`

Record time-stamped probes for research, Codex `image_gen`, real transparent PNG output, assembly backend, and render/inspection. Before S7, generate a small test asset and validate the file itself has PNG alpha; a prompt that merely asks for transparency is not proof. If PPTX is requested, verify one assembly backend and use only that backend for the run.

### `concept-generation-log.json`

For every production contentful concept, record the slide ID and immutable version, exact prompt, `codex-image_gen` tool/model identity when available, selected calibration variant ID, visual strength, layout density, every attached reference ID/path/SHA-256, output path/SHA-256, and status. `copy_map` records every visible word and an exact title mapping to the approved storyboard. A long storyboard `message` is a narrative claim, not automatically a line that must appear verbatim on-screen. When concise visible copy realizes it, mark all realization items with `storyboard_field: message` and record `message_mapping` using the same contract as calibration; other copy cites a source quote or explicit paraphrase for G4 review. `source_lineage` accepts any user-authoritative source format plus the approved storyboard or brief; each source has a project-local path, SHA-256, approved/verified status, and locator. `image_inventory` classifies representative imagery as `illustrative`, `verified-source`, or `pending-placeholder`; illustrations are labeled and never used as evidence, while factual images link to unchanged, hash-verified sources. `text_review` records observed text per copy ID and a transcript artifact/hash. If deterministic overlays repair glyphs, retain the prior image and record input/output hashes and overlay evidence. The validator checks records and hashes; metadata or OCR alone is not proof that an image is correct. G4 binds the log, transcript evidence, source files, contact sheet, and every contentful image. The output must match its `concept_path`.

### `deck-spec.json`

At the root, add `production_estimate` with unique component count, planned generation calls, reserved retries, and estimated completion when a deadline exists. At inventory/release, reconcile it with manifest asset count and each generated asset's `generation_attempts`.

Each slide requires:

- `id`, `title`, `message`
- `concept_path` after S5, pointing to the current contentful review concept, not its textless master
- `components`: stable component IDs
- `fill_slots`: stable ID, kind, normalized `[x,y,w,h]`, and exact editable `content` for ordinary text (except an action-title may inherit the slide title); deliberately blank ordinary text declares `user_fill_required: true`, while `ordinary-data` content stays empty for user entry
- `composition`: layout archetype, complexity (`sparse`, `standard`, or `rich`), information units, visual layers, selected reference IDs, and variation from the previous slide
- `readability`: every ordinary text/data fill slot's planned font and line count, the usable main-visual bbox, any specific underfloor exception, and a 100%-scale review record bound to the current contentful image hash from the Concept stage
- for semantic-system v2 projects, each ordinary `readability.text_regions[*]` has a `font_role` referencing the approved text token, with matching readability role and exact point size; `semantic_design.region_slots` binds each repeated title/key-message/qualifier region to a fill slot; `semantic_design.frame_instances` declares meaningful frames and visible label slots; `semantic_design.exceptions` names justified anchor/coverage deviations, never a silent type or truth exception
- optionally `speaker_notes`, `citations`, `transition`, `accessibility_notes`

`speaker_notes` is optional plain text, not an array or Markdown sidecar locator. Omission/empty text means no notes. `brief.json.delivery.speaker_notes: required` makes non-whitespace notes mandatory for every slide; the absent field or `not-requested` preserves earlier projects' optional behavior. Normalize CRLF/CR to LF; reject XML-invalid control characters. Assembly embeds the text and records `speaker_notes_sha256` for nonempty notes, then checks the real notes body against the current spec. See `narrative-and-speaker-notes.md` for content and verification rules.

Normalized coordinates are in the range 0..1 and must stay within the canvas.

For a production deck, ordinary content slides meet the approved composition-profile minimums. Sparse slides are limited to approved roles. When the deck has enough pages, use the approved minimum number of layout archetypes, do not exceed the consecutive-repeat limit, and include a rich content slide unless an approved restrained direction says otherwise. Counts are planning evidence, not a loophole: G4 and QA verify that units and layers are meaningful in the render.

At G4 for a v2 project, include `cross_slide_semantics_review` in the approval packet. Compare the contact sheet and every full-size page against the same role meanings, native type tokens, frame status labels, and repeated-region anchors. A slide-specific anchor exception is explicitly listed in `slide_specific_deviations`; it does not alter the token's meaning or font size. The G4 approval is stale when its style system, deck bindings, copy log, or reviewed image changes.

### `scene-graph.json`

Each slide records its canvas and every visual element:

- `component_id`
- globally unique `instance_id`; repeated placements may reuse one `component_id`
- normalized `bbox: [x,y,width,height]`
- integer `z`
- optional `rotation`, `opacity`, `crop`, `blend_notes`, `reused_from`

Run two passes: semantic inventory first, residual pixel inventory second. The second pass catches decorative fragments, shadows, separators, masks, and connectors omitted by semantic labeling.

### `component-master-manifest.json`

Create this only after the current G4 approval. Page workers may prepare separate master records concurrently, then the main agent merges one record per deck slide in deck order. Record one textless master per slide with its versioned path/hash, approved contentful concept path/hash, and current approved `concept-generation-log.json` hash. Set `text_policy: textless`, `ordinary_text_removed: true`, and `contains_ordinary_text: false`. `preserved_fill_slots` must exactly match the slide's fill-slot IDs, kinds, and normalized bounding boxes in `deck-spec.json`. Add a `geometry_review` with a separate side-by-side comparison image path/hash, real reviewer, 100%-scale passed status, hashes of both reviewed images, and passed composition/fill-slot/text-removal checks before that slide's inventory. Strict mode requires a human reviewer; user-authorized local mode may record agent QA and still presents the complete packet for the single decomposition decision. Never use a contentful concept as a component master or final flattened slide.

### `decomposition-map.json`

Create after the current G4 and textless-master geometry review. `version` and one `slides` record per deck slide are required. Each slide binds `concept_path`/`concept_sha256` to the G4-approved image and `master_path`/`master_sha256` to the current textless master. Number every item with a stable `id`, human-readable `label`, normalized `bbox`, `inventory_pass: semantic|residual`, and a treatment decision. A `visual` item names its `role`, `source_class: design-object|ordinary-photo|truth-sensitive`, `component_id`, unique `instance_id`, `z`, `occlusion`, `overlaps`, four normalized `crop_padding` margins, `contains_ordinary_text_or_data`, `text_data_decision`, and treatment (`preserve-pixels`, `reconstruct-single`, `preserve-source`, `photo-adjust`, or `blank-content` as appropriate). If a design object contains ordinary text/data, its decision must blank that content and reconstruct one object. A `fill-slot` item names its `fill_slot_id`, matching kind/geometry, and `treatment: editable`. An intentionally omitted visible item needs a reason. Reuse one component asset through distinct scene instances, never by assigning two independent objects to one instance.

Page workers may draft separate decomposition and scene records concurrently. The main agent checks that the frozen G4 concept hashes and deck-slide IDs still match, all expected pages appear exactly once, instance and fill-slot IDs are unique, and reuse references agree; then it writes `decomposition-map.json` and `scene-graph.json` once in deck order. The `review_image` is the concept at original pixel dimensions with item numbers and SHA-256; `review_packet` is a Markdown table with its own hash. Both record `reviewed_items_sha256` for the current numbered item list; the list itself prints that digest and a row for each ID. Generate them with `scripts/render_decomposition_review.py <project-dir> --slide <id>` after checking Pillow is available. This command rewrites the shared decomposition map, so the main agent runs it serially after the merge. The renderer refuses missing/stale G4 or master geometry evidence and will not overwrite a different review at the same versioned path. Record `coverage_review` with a real reviewer and passed semantic, residual, and independence checks plus an empty `missing_items` list. The renderer does not grant approval. The public validator checks IDs, image dimensions, list rows, geometry, references, coverage declarations, file hashes, and gate staleness; it cannot infer from pixels whether an undeclared object was overlooked or one transparent PNG contains two semantic objects. The human must inspect the full-size image and later isolation proofs.

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
- `generation_attempts` and `generation_history` for generated assets: one unique call ID and requested component ID per call, retained output path/hash and accepted/rejected status, with exactly one accepted call matching the current output
- `extraction.route` matching every approved decomposition item that reuses the asset; `preserve-pixels` additionally records one source slide/item, current textless-master path/hash, full-size mask path/hash, pixel crop coordinates, and output path/hash. Re-extraction archives the old record in `extraction_history`; historical files and hashes remain verifiable.
- Ordinary photos require a G1 hash-locked `source_rights_confirmation` that also explicitly classifies the exact source as non-truth-sensitive `ordinary-photo` (not screenshot, data figure, or report), plus matching `source_photo: {path, sha256}`. `photo_output_mode: rectangle` uses `role: ordinary-photo`, `output_class: opaque-photo-rectangle`, `background_requirement: opaque-rectangle`, and an opaque PNG/JPEG; `photo_output_mode: cutout` uses `role: photo-cutout`, `output_class: transparent-photo-cutout`, `background_requirement: transparent`, and a real-alpha PNG. Incidental text within an approved ordinary photo is source content, not a generated slide label; preserve it. Source-preserved rectangles must byte-match the source. `photo-adjust` keeps `photo_processing` diagnosis evidence, exact source-bound `确认照片后期方案` with the diagnosis and preservation-recipe hashes, direction, preservation prompt/recipe, and each immutable attempt; it also requires a current passed `photo_review` with deterministic native-size source/output image and explicit identity, architecture, perspective, key-scene, factual-content, and source-text checks. Both modes still need a passed standard isolation review. Machine checks verify records and pixels, not semantic identity or rights authenticity.
- `editability`: `component-editable` for independent visual objects (including opaque photo rectangles and transparent PNGs), `native-editable` for approved native objects, or `fixed-evidence` for preserved factual assets
- `sha256`
- alpha metadata when transparency is promised; opaque photo rectangles are verified as fully opaque instead
- `isolation_review` for visual assets: current asset and mapped-item hashes, generated concept-crop/light-checker/dark-ground image and readable list paths/hashes, a real reviewer, passed status, and explicit single-object, neighbor-residue, ordinary-text/data, edge, and concept-match checks
- status and retained failed/replaced extraction and review evidence

At `assets`, a visual asset is not approved by alpha alone. `scripts/render_asset_isolation_review.py` builds a review sheet for every use of one asset; the validator recomputes its pixels and checks the declared review authority. Strict mode requires a human decision; user-authorized local production may record an actual agent inspection with the explicit local review mode and a timezone-aware review time. It cannot derive semantic independence from connected pixels. A `preserve-pixels` component is deterministically extracted from one unoccluded textless-master object through a full-size single-object mask; source RGB must match under the mask and a clear transparent border is required. Occluded, fused, or ordinary-text/data-bearing design objects use `reconstruct-single`, with one component per image-generation call. Previous attempts and evidence remain addressable at immutable paths.

After the pilot passes, page workers may produce distinct components and asset-record fragments concurrently in disjoint slide-owned paths. `render_asset_isolation_review.py --manifest-fragment page-shards/<batch>/<slide-id>/asset-manifest.fragment.json` writes the pending isolation record to that page's fragment, so different pages can prepare evidence concurrently. Without this option the renderer writes the shared manifest and must remain single-owner. The main agent runs `merge_page_assets.py --batch <batch>` once to reject duplicate/conflicting asset IDs, stale output hashes, and unreviewed records, then runs `--stage assets`. The shared manifest and final PPTX are never multi-writer outputs.

Role rules:

- `table-shell` and `chart-shell`: `content_policy: blank-fill-slots`, `contains_text: false`, `contains_data: false`, and non-empty `fill_slot_ids`
- all roles except `special-typography`: no embedded ordinary text
- `special-typography`: `exact_text`, language, OCR result, and `human_approved`
- truth-sensitive sources: preserve unchanged or blank their variable content; record the decision

Truth-sensitive assets record `source`, `source_sha256`, output hash, and preservation strategy. Exact-preservation strategies must hash-match the source.

Allowed truth-sensitive strategies are `preserved-raster`, `preserved-vector`, and `preserved-truth-sensitive`. Masked alteration is intentionally blocked until a deterministic mask-outside pixel comparison is available. “Decomposition” normally means reference-guided per-component regeneration, not lossless pixel-layer extraction; state this limitation in G3/G4.

The pilot gate applies to production runs requesting PPTX. Component-library-only runs continue to `assets` after the decomposition gate without a trial PPTX.

### `assembly-map.json`

For each slide record component IDs, fill-slot IDs, unique continuous `output_index`, optional `pptx_part`, backend, and `flattened_concept_used: false`. If PPTX is requested, run the object-level assembler after `assets` passes and record the output path/SHA-256; hashes of the exact deck spec, scene graph, asset manifest, and style contract; one object record per scene instance; one native text-box record per fill slot; and a 1920×1080 render per slide bound to the PPTX hash. Keep status `structure-assembled-visual-review-pending` until the next full-size visual QA gate explicitly sets `visual-review-passed`; QA validation rejects a still-pending assembly. Validation checks required Office package parts, XML readability, actual relationship order, expected slide count, a media whitelist bound to approved manifest assets, concept-image hashes, near-full-slide raster pictures, and each PPTX picture/text box's identity, bytes, placement, order, rotation, copy, and font size. For v2 semantic-system projects it also checks native font family, weight, and color against the role token. The scene graph governs placement; do not tune positions only inside the PPTX without updating it. Reassembly creates a new version rather than overwriting an approved file.

The single-slide pilot uses the same object-level assembler with `--pilot-slide`, but writes an immutable `pilot/<version>/pilot-assembly-map.json` and PPTX rather than the final full-deck `assembly-map.json`. Pilot preflight checks only the selected slide's ready assets while requiring the approved full-deck G4/decomposition contracts. Production pilot review requires an actual PowerPoint render; `--no-render` is diagnostic and cannot pass it. `pilot-review.json` records a human decision in strict mode or an actual declared agent inspection under authorized local mode; alpha or structural PASS cannot create that review.

### `qa-report.json`

Record overall status, per-slide status, checks performed, evidence files, differences from the concept, exceptions, repairs, and final reviewer. For PPTX, `prepare_deck_qa.py` generates a pending-human packet for **every** slide: current full-size contentful concept, actual 1920×1080 PPTX render, 3840×1080 side-by-side, 1920×1080 overlay, and a readable page checklist. In production, it also independently re-renders the current PPTX with PowerPoint and pixel-compares each declared render; the verified renders remain in the QA evidence package. The contact sheet is generated from all current PPTX renders in deck order, not from the concept images. Each page's bindings hash its concept, render, deck/scene/assembly slide, style, used assets, and PPTX; all nine formal checks cover independent objects, geometry, hierarchy, color/z-order, content truth, visual relationships, full-size readability, main-image space, and editability. The five whole-deck formal checks cover reference transfer, composition richness, full-size readability, visual coherence, and truth consistency, and bind the reference study, story, style, deck, PPTX, and contact sheet. Per-page formal `passed` requires a human reviewer and timezone-aware timestamp. Any unresolved blocker/major or over-three-retry defect blocks QA; minor exceptions are explicitly listed for G5 acceptance. `finalize_deck_qa.py` checks current evidence pixels and hashes before setting formal visual QA passed; it never grants G5. Production release requires explicit `reference-transfer`, `composition-richness`, and `readability-full-size` checks. Release also requires `final_contact_sheet`, `exception_register`, and `deliverable_index` paths. G5 approval hashes those three files plus every global and per-slide QA evidence file. For PPTX, `subject_sha256` binds QA to the assembled file. A declared exception identifies the owner, reason, and user acceptance.

For a user-authorized local draft, parallel child-agent page checks may be merged into a separate agent-QA record bound to the PPTX hash, each render hash, reviewed slide IDs, actual reviewers, and whole-deck contact sheet. This does not change `qa-report.json` from pending-human, satisfy `--stage qa`, or grant G5. The delivery PPTX retains a draft label; do not enter child-agent names into human reviewer fields.

The executable local-draft contract is `agent-qa-report.json`, described in `local-agent-qa.md`. Export and `--verify` run the current assembly validator and then the actual formal QA/release validator or this authorized agent route. Complete current agent inspection with P1 findings may export an unpassed draft and its linked project-side problem record; P0, incomplete inspection, or stale evidence blocks. The three-folder handoff adds no extra QA file or folder.

## Transition ownership

- Research defects return to S1.
- Story hierarchy defects return to S2.
- Style inconsistency returns to S3 or the specific concept in S5.
- Missing/merged components return to S6.
- Alpha, crop, or isolated-asset defects return to S7.
- Placement and stacking defects return to S8.
- QA never repairs files silently; it identifies the owning stage.

The action-title and storyboard discipline is informed by [SlideSage](https://github.com/vedraut/slidesage); this skill adds explicit research evidence, human gates, and component decomposition contracts.
