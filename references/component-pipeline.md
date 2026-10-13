# Concept-to-component pipeline

> Scope: This detailed transparent-PNG inventory and decomposition route is the legacy component-first contract for users who need separately movable/recombinable visual layers. `showcase-v1` may use mixed native PPTX objects; see [hybrid-object-design.md](hybrid-object-design.md).

Apply [visual-qa-tolerance.md](visual-qa-tolerance.md) when deciding whether a reconstructed component matches the concept. Exact master pixels are a property of the `preserve-pixels` route; a reconstructed stroke, glow, or texture does not need pixel identity to pass.


For a project with explicit low-friction local-production opt-in, keep all concept, master, decomposition, isolation, and trial evidence, but perform subsequent reversible local checks with agent QA instead of asking for a fresh user reply per asset or trial. Record the real reviewer and do not call agent QA human approval. The initial current decomposition approval remains required.

## 1. Freeze the G4-approved contentful concept

Treat the approved contentful concept as the canonical visual reference for copy, truth labels, imagery, and composition. G4 binds its version, path, image hash, copy map, source lineage, text-review transcript, and contact sheet. Any revision uses a new image path and keeps the former image as history; affected G4 and downstream artifacts must be approved again.

## 2. Derive the textless component master after G4

Only after the current G4 approval, create one textless component master per slide. Different slides may run this step concurrently in disjoint page shards; each slide still follows its own master → geometry review → inventory order. Remove ordinary titles, body copy, labels, values, and data while preserving the approved composition and each fill-slot coordinate. Record the master path/hash, approved contentful image path/hash, concept-log hash, version, and fill-slot geometry in `component-master-manifest.json` after the single-owner merge. Before that slide's inventory, compare the contentful concept and textless master side by side at 100% scale, save a separate comparison image, and record the actual reviewer, evidence hash, both reviewed image hashes, and explicit composition/fill-slot/text-removal checks in `geometry_review`. Strict mode uses human geometry review; a user-authorized local draft may record agent QA without calling it human approval. The one full-deck decomposition decision still includes every page's current geometry evidence. The validator enforces those links and the review record; metadata alone cannot prove visual equivalence.

Before production, prove the selected image route can create a real transparent PNG with a small test call and record it in `capability-report.json`. Reference-guided generation is reconstruction, not guaranteed lossless layer extraction.

## 3. Inventory in two passes

Compare both the approved contentful concept and its textless master. The concept preserves approved message and source context; the master exposes the blank geometry used for editable copy and later extraction.

### Pass A — semantic inventory

List items a designer would name: hero illustration, person cutout, icon, arrow, chart shell, table shell, diagram node, panel, special title art.

### Pass B — residual inventory

Compare the concept against Pass A and capture visible leftovers: shadows, glow fragments, texture patches, corner ornaments, separators, masks, dots, underlines, badges, arrowheads, and background motifs.

For each item, decide:

- component or fill slot;
- unique or reused;
- generated, preserved unchanged, or omitted;
- bbox, z-order, crop padding, and overlap relationships;
- whether it is truth-sensitive;
- whether it contains ordinary text/data that must be blanked.

Do not merge components merely to reduce call count if the user needs to recombine them independently.

Write each page's draft inventory to its disjoint page shard as one numbered item per independently movable object, editable fill slot, or explicitly omitted visible element. The main agent merges current page records once, in deck order, into `decomposition-map.json` and `scene-graph.json`. Match every visual item to one unique scene instance and its asset role; repeated approved asset files may have multiple distinct instances. Record source class, extraction/reconstruction treatment, bbox, z-order, occlusion, overlaps, and whether the item was found in the semantic or residual pass. Reject missing pages, duplicate IDs, stale concept hashes, and conflicting reuse before the merge.

After the canonical merge, the main agent runs `scripts/render_decomposition_review.py <project-dir> --slide <id>` for each page: the current script writes `decomposition-map.json`, so do not invoke it concurrently against one project. The page-local master and inventory work remains parallel; this short shared-map write is serialized. Show all numbered images and Markdown tables to the user in one packet. Correct omitted connectors, background fragments, merged objects, or wrong photo boundaries and regenerate only affected page evidence. Record the human semantic/residual coverage and independence decision once for the complete packet, then require a current explicit `run-state.json.gates.decomposition` approval bound to the map, concept, master, and review evidence. `--stage inventory` checks the draft; `--stage assets` blocks before the approval. A script can prove declared links and hashes, not discover an item omitted from both maps or decide semantic independence from pixels.

Only after this approval, select a provider from `visual-provider-registry.json` and run its PPT adapter. For Material Illustration, the adapter itself rechecks the current explicit post-G4 decomposition approval and maps each request to an approved `reconstruct-single` design object with matching role and bbox before emitting any generator-ready prompt. It must also reject truth-sensitive requests, unsupported page/component roles, caller-written component prompts, embedded output text/data, opaque output contracts, and table/chart shells without valid blank fill slots. The adapter derives the actual extraction prompt only from the approved reference, normalized crop, and component role. Merge only accepted adapted records into the asset manifest.

## 4. Create a crop reference

For each component, prepare the full concept plus a local crop/reference when possible. The full concept preserves style and role; the crop disambiguates the target. Do not use a crop that cuts off the intended silhouette.

For `preserve-pixels`, prepare a full-master-size grayscale PNG mask of exactly one unoccluded, textless design object. The mask is an explicit selection, not proof that the selection excludes a neighboring semantic object. Keep it versioned and inspect it against the approved concept and textless master. Run `scripts/extract_preserved_component.py <project-dir> --slide <id> --item <id> --mask <project-relative-mask.png>` only after the decomposition gate is current. The extractor copies source RGB exactly under that mask, rejects out-of-crop material and clipped borders, and records source/mask/output paths, hashes, and crop coordinates. Re-extraction must use a new output path; the old extraction metadata and file remain verifiable in `extraction_history`. It does not approve the component.

## 5. Reconstruct one isolated component per call when preservation is not valid

For a partially occluded, fused, or ordinary-text/data-bearing design object, use Codex built-in `image_gen` with the installed `imagegen` skill. Each call requests exactly one component on a fully transparent canvas with generous transparent padding. Do not label reference-guided reconstruction as original-pixel extraction. Record a unique call ID, requested component ID, immutable output path/hash, and accepted/rejected status for every attempt; one accepted attempt points to the current asset file. Reused placements reference that same asset rather than repeating a call.

Required constraints:

- target object only;
- no neighboring objects, background scene, frame, mockup, labels, or watermark;
- preserve the concept's silhouette, palette, material, lighting, viewpoint, and edge treatment;
- alpha transparency, not a white checkerboard or simulated background;
- no cropped edges or contact shadows that imply an opaque floor unless explicitly part of the object;
- no text unless role is `special-typography`;
- no real or invented values/data.

If the result contains extra material, repair or regenerate the individual asset rather than editing the concept.

## 6. Special role rules

### Tables

Generate only the table shell: outer frame, cell grid, fills, borders, headers as blank colored regions, and approved decoration. Remove every word, number, icon-label pair, footnote, and data mark. Each content region becomes a fill slot.

### Charts and data graphics

Generate only non-data styling requested by the user. Remove values, tick labels, category labels, legends, annotations, and any bar/line/point geometry that encodes actual data. When even empty axes could mislead, use a blank framed plot area with separately generated decorative elements.

### Arrows and basic shapes

Generate arrows, connectors, circles, pills, polygons, brackets, callouts, and similar geometry as separate transparent PNGs when they are visible components. Preserve the approved style and orientation. Do not replace them with native slide shapes unless the user changes this rule.

### Special typography

Use only for a short, deliberate wordmark or decorative phrase. Lock `exact_text`; request one finished isolated asset; prohibit alternate spellings and unrelated text; verify with OCR and human review. Ordinary headings and body copy stay editable fill slots.

### Ordinary photographs

First record rights **and** a human ordinary-photo classification for the exact source hash; product screenshots, data figures, reports, and ambiguous factual images never enter the photo-postprocessing route. `ordinary-photo` is one opaque rectangular image object (`photo_output_mode: rectangle`, `output_class: opaque-photo-rectangle`), while `photo-cutout` is one real-alpha PNG (`photo_output_mode: cutout`, `output_class: transparent-photo-cutout`). Do not call the first a transparent component or use a full-slide photo as a flattened background. Both need an approved decomposition item and concept/isolation review; the rectangle remains an independent scene instance for later PPTX assembly.

For a source-preserved rectangle, keep the bytes unchanged. For `photo-adjust`, follow `photo-postprocess-coach`: inspect and measure the original, present a repair/style direction and preservation recipe, obtain separate `确认照片后期方案` bound to the source, diagnosis hash, direction, and recipe hash, and then use the original as the editing source. Limit edits to exposure, tone, color, noise, permitted crop, or subject isolation while preserving identity, architecture, perspective, and key scene content. Keep diagnosis evidence, selected direction, source-bound confirmation, preservation prompt/recipe, and every attempted output path/hash. Run `scripts/render_photo_review.py <project-dir> --asset <id>` to show original and result side by side at native size; record all human preservation checks against both hashes. An image model's output and a passing metric cannot by themselves prove identity preservation.

### Truth-sensitive visuals

Preserve a supplied factual visual pixel-for-pixel if reuse is permitted. If values must be user-entered later, blank the factual content and retain only the approved shell. Do not hallucinate a substitute.

Preserve the approved raster/vector byte-for-byte. These assets may remain rectangular and need not be forced through transparent regeneration. Do not mask or alter truth-sensitive pixels until a deterministic outside-mask comparison is available.

## 7. Validate and approve

For each transparent asset (and each photo where applicable):

- verify file exists and compute SHA-256;
- verify an alpha channel and meaningful transparent pixels only when transparency is promised; opaque photo rectangles must have no transparent pixels;
- inspect edges at high contrast for white/black halos;
- compare against concept crop for meaning, shape, palette, orientation, and relative detail; classify visible differences as P0/P1/P2 at presentation size, not by pixel count;
- run OCR when text is prohibited and for all special typography;
- confirm its manifest role and content policy;
- render `scripts/render_asset_isolation_review.py <project-dir> --asset <id>` and show its concept crop plus the asset on a light checkerboard and dark ground, with a readable row for every placement that reuses it;
- record `single_object`, `no_neighbor_residue`, `no_ordinary_text_or_data`, `edge_clean`, and `concept_match` against the current asset and item hashes; mark `approved` only after all pass. Strict mode uses a human reviewer; a user-authorized low-friction local draft may use an explicitly labeled agent reviewer.

The public validator recomputes the isolation sheet, checks the review list and hashes, binds extraction route to the approved item, verifies the original-pixel route against the current master and mask, and checks one-component generation-call history. It cannot infer whether two visible shapes are separate semantic objects or whether the OCR missed a glyph. A transparent PNG with two operable objects fails the human single-object check even if its alpha channel is technically valid.

## 8. Repair loop

Use at most three focused repair attempts for a persisting P0/P1 defect class. Pass P2 cosmetic differences without further attempts. Keep the best prior version. If a material defect persists, record a blocker with evidence and request a human decision; never flatten the entire slide to hide the failure.

## Design provenance

The canonical-master, scene-graph, transparent-asset, and focused-repair pattern is informed by [paper-figure-skill](https://github.com/Thanx01/paper-figure-skill). The resumable manifest and anti-flattening rules are informed by [image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill). This skill deliberately changes their defaults where needed: arrows and basic shapes are transparent PNG components because the user wants to regroup them manually.
