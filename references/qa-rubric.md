# QA rubric

QA is layered. Do not collapse structural validation, visual comparison, truth review, and release acceptance into one subjective score.

## A. Contract checks

Run the validator at the current stage. Release requires:

```bash
python scripts/validate_project.py <project-dir> --stage release
```

Any failure blocks transition.

The concept gate also checks contentful copy/source lineage, source and image hashes, text-review transcripts, and the G4 binding. It checks declared point sizes, usable image-frame geometry, and each current concept's 100%-scale review record; G4's `readability_review` supplies the human visual decision. Inventory rejects a component master that predates G4 or changes the approved fill-slot geometry.

## B. Asset checks

For every manifest asset:

- file exists and hash matches the manifest;
- RGBA/alpha exists, decoded transparent pixel ratio matches the manifest, visible content exists, and the outer pixel border is transparent;
- edges have no matte halo or accidental opaque rectangle;
- exactly one requested object is present;
- role and content policy match the manifest;
- no ordinary text or data is embedded;
- table/chart shells are blank;
- arrows and basic shapes are transparent PNGs;
- special typography passes OCR and has human approval;
- truth-sensitive visuals are unchanged or intentionally blanked.

## C. Inventory checks

Compare the G4-approved contentful concept, textless component master, semantic inventory, residual inventory, scene graph, and manifest:

- every visible concept item maps to one component or fill slot;
- every manifest asset appears in the scene graph;
- no component is accidentally merged with a neighbor;
- repeated assets declare reuse rather than silently duplicating identity;
- z-order and overlaps are explicit.
- the contentful concept and textless master have matching composition and reserved fill-slot geometry;
- ordinary copy/data is removed from the master, while verified source imagery remains exact and pending evidence stays labeled as a placeholder.

## D. Content and text checks

- compare every visible title, body line, and truth-status label with its `copy_map` entry;
- confirm title/message wording matches the approved storyboard and other claims cite a verified/approved source locator;
- inspect the actual image against the hash-bound transcript and any deterministic overlay evidence; a recorded OCR result by itself is not a pass;
- confirm illustrative imagery is labeled and never appears as factual evidence.

## E. Assembly checks

Render the assembled output and compare with the approved concept using:

1. side-by-side view;
2. low-opacity overlay;
3. difference view when available;
4. whole-deck contact sheet.

Check geometry, crop, orientation, color, hierarchy, whitespace, fill-slot usability, missing assets, overflow, and clipping. Confirm `flattened_concept_used: false`. For PPTX, verify the package opens, page count matches, QA is bound to its SHA-256, and approved concept renders are not embedded as media.

For production release, record `readability-full-size` after inspecting the actual assembled text and image regions at presentation size, not just the concept or a contact sheet. Compare the usable image pane and text sizes with the G4-approved record. Repair by reducing copy, truthful cropping/enlargement, recomposition, or splitting a slide; do not conceal crowding by shrinking.

## F. Communication and accessibility checks

- title-only narrative still works;
- each slide communicates one message;
- reading order is clear;
- color contrast and non-color cues are adequate for the intended audience;
- citations or evidence IDs remain traceable;
- placeholders clearly distinguish editable text/data from artwork;
- no generated decoration is mistaken for factual data.

## G. Reference and richness checks

- selected references are analyzed and hash-locked, not just named;
- production concept logs contain the exact prompt and attached selected reference paths/hashes;
- rendered slides transfer the approved reference grammar without copying distinctive finished compositions, logos, characters, or source text;
- every declared information unit and visual layer is meaningful and visible;
- ordinary content slides meet the approved composition-profile thresholds;
- sparse pages occur only in approved narrative roles or declared G4 deviations;
- layout archetypes vary at the approved rhythm, while palette, type, spacing, and visual family remain coherent;
- a page is not accepted merely because JSON counts were satisfied with decorative fragments.

## Severity

- **Blocker**: false/missing evidence, concept used as flattened final, ordinary text/data embedded in final component art, missing component, unapproved special typography, missing production reference provenance, unreadable output, or validator failure.
- **Major**: significant composition drift, wrong hierarchy, unusable fill slot, transparency defect, or accessibility failure.
- **Minor**: small spacing, edge cleanup, or non-semantic visual mismatch.

Release requires zero blockers and zero majors. Minors must be fixed or explicitly accepted at G5.

## Repair ownership

Record each issue with slide/component ID, evidence image/path, severity, owner stage, repair attempt count, and disposition. Repair the smallest owning artifact. Do not hide a defect by flattening the slide.
