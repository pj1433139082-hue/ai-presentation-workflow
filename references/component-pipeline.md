# Concept-to-component pipeline

## 1. Freeze the G4-approved contentful concept

Treat the approved contentful concept as the canonical visual reference for copy, truth labels, imagery, and composition. G4 binds its version, path, image hash, copy map, source lineage, text-review transcript, and contact sheet. Any revision uses a new image path and keeps the former image as history; affected G4 and downstream artifacts must be approved again.

## 2. Derive the textless component master after G4

Only after the current G4 approval, create one textless component master per slide. Remove ordinary titles, body copy, labels, values, and data while preserving the approved composition and each fill-slot coordinate. Record the master path/hash, approved contentful image path/hash, concept-log hash, version, and fill-slot geometry in `component-master-manifest.json`. Before inventory, a human must compare the contentful concept and textless master side by side at 100% scale, save a separate comparison image, and record the reviewer, evidence hash, both reviewed image hashes, and explicit composition/fill-slot/text-removal checks in `geometry_review`. The validator enforces those links and the review record; metadata alone cannot prove visual equivalence.

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

After inventory, select a provider from `visual-provider-registry.json` and run its PPT adapter. For Material Illustration, the adapter must reject truth-sensitive requests, unsupported page/component roles, caller-written component prompts, embedded text/data, opaque output contracts, and table/chart shells without valid blank fill slots. The adapter derives the actual extraction prompt only from the approved reference, normalized crop, and component role. Merge only accepted adapted records into the asset manifest.

## 4. Create a crop reference

For each component, prepare the full concept plus a local crop/reference when possible. The full concept preserves style and role; the crop disambiguates the target. Do not use a crop that cuts off the intended silhouette.

## 5. Generate one isolated component per call

Use Codex built-in `image_gen` with the installed `imagegen` skill. Each call requests exactly one component on a fully transparent canvas with generous transparent padding.

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

### Truth-sensitive visuals

Preserve a supplied factual visual pixel-for-pixel if reuse is permitted. If values must be user-entered later, blank the factual content and retain only the approved shell. Do not hallucinate a substitute.

Preserve the approved raster/vector byte-for-byte. These assets may remain rectangular and need not be forced through transparent regeneration. Do not mask or alter truth-sensitive pixels until a deterministic outside-mask comparison is available.

## 7. Validate and approve

For each asset:

- verify file exists and compute SHA-256;
- verify an alpha channel and meaningful transparent pixels;
- inspect edges at high contrast for white/black halos;
- compare against concept crop for shape, palette, orientation, and relative detail;
- run OCR when text is prohibited and for all special typography;
- confirm its manifest role and content policy;
- mark `approved` only after checks pass.

## 8. Repair loop

Use at most three focused repair attempts for one defect class. Keep the best prior version. If the defect persists, record a blocker with evidence and request a human decision; never flatten the entire slide to hide the failure.

## Design provenance

The canonical-master, scene-graph, transparent-asset, and focused-repair pattern is informed by [paper-figure-skill](https://github.com/Thanx01/paper-figure-skill). The resumable manifest and anti-flattening rules are informed by [image-to-editable-ppt-skill](https://github.com/ningzimu/image-to-editable-ppt-skill). This skill deliberately changes their defaults where needed: arrows and basic shapes are transparent PNG components because the user wants to regroup them manually.
