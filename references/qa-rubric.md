# QA rubric

> Scope: This rubric's production scores and strict thresholds apply to the legacy production profile. `showcase-v1` uses concrete technical checks and actual-render agent review, not a numeric score as a proxy for taste.

QA is layered. Do not collapse structural validation, visual comparison, truth review, and release acceptance into one subjective score.

For visual acceptance, use [visual-qa-tolerance.md](visual-qa-tolerance.md). P0 truth/structure failures block, P1 defects obvious at presentation size get repaired, and P2 line-width/pixel-level differences pass. Overlays and difference views are diagnostic, not a pixel-perfect acceptance gate.

## A. Contract checks

Run the validator at the current stage. Release requires:

```bash
python scripts/validate_project.py <project-dir> --stage release
```

Any failure blocks transition.

The concept gate also checks contentful copy/source lineage, source and image hashes, text-review transcripts, and the G4 binding. It checks declared point sizes, usable image-frame geometry, and each current concept's 100%-scale review record; G4's `readability_review` supplies the human visual decision. Inventory rejects a component master that predates G4 or changes the approved fill-slot geometry.

For semantic-system v2 projects, the validator also checks that every slide binds ordinary text to one approved type role, repeated title/key-message/qualifier regions use the declared slots and anchors, status frames use declared roles with labels, and native PPTX text properties match the role tokens. G4's cross-slide semantic review remains a human decision: metadata alone cannot inspect a generated border or decide whether a key sentence communicates the right claim.

At G4, inspect each evidence placeholder and each ordinary module card at 100% scale: neither may borrow the verified status frame's solid cobalt perimeter or corner brackets. If a blank evidence slot looks verified, repair the concept before approval, retain the prior image as a versioned record, and rebind the review sheet to the repaired hash. A visible `已验` label plus the declared border treatment is needed for a verified status frame; a thin generic card border alone is not a truth claim.

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
- If presenter notes are included, inspect their claims, qualifications, and slide-ID mapping as content too. Verify actual PPTX notes match the current deck spec; requested notes cannot be satisfied by an external script alone.

## E. Assembly checks

Before batch production, the representative-page pilot uses the same comparison checks against the actual one-slide PPTX render. Inspect the approved contentful concept and actual render at presentation size; use isolated components and the 100%-scale side-by-side/overlay to investigate suspected P0/P1 defects. Record the seven checks in `pilot-review.json`: independent single-object identity, no missing objects, placement, seams, color/z-order, text/main-image space, and factual labels. A valid alpha channel does not prove that two objects are separable. Large offsets, omitted arrows, and fused objects are blockers. P2 stroke, edge, and texture differences pass. `--stage pilot` must pass before production expands to the remaining pages.

Render the assembled output and compare with the approved concept using:

1. side-by-side view;
2. low-opacity overlay;
3. difference view when available;
4. whole-deck contact sheet.

For PPTX, `prepare_deck_qa.py` generates these for every page from the actual full-size PowerPoint renders and leaves them `pending-human`. In production it independently re-renders the current PPTX with PowerPoint and rejects any declared render whose pixels differ; this checks evidence integrity, not fidelity to the concept. Inspect every page at presentation size, opening 100%-scale pairs for suspected P0/P1 issues. Fill the nine per-page checks and five whole-deck checks (reference transfer, composition richness, readability, coherence, truth), reviewer, timestamp, and issue records in `qa-report.json`; a one-page pass cannot clear the rest of the deck. `finalize_deck_qa.py` verifies the present concept/render/evidence pixels and hashes and only then marks assembly visual review passed. This technical QA pass still awaits separate G5 `确认发布`.

Page inspection may run concurrently in disjoint read-only child-agent shards under the parallel-review contract in `SKILL.md`. Each shard reports its actual reviewer and P0/P1 findings against frozen evidence hashes; only the main agent merges records and checks the full-deck contact sheet. One complete page pass is enough. A child-agent review is agent QA for a local draft or preparation for a strict-mode human packet; it never becomes human approval merely because several agents agreed. The existing `finalize_deck_qa.py` path remains for the separately completed formal QA record.

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
- a title, bottom takeaway, status qualifier, or frame treatment never changes its semantic meaning or native type token between pages; declared opening/closing placement exceptions do not change role meaning;
- a page is not accepted merely because JSON counts were satisfied with decorative fragments.

## Severity

- **Blocker**: false/missing evidence, concept used as flattened final, ordinary text/data embedded in final component art, missing component, unapproved special typography, missing production reference provenance, unreadable output, or validator failure.
- **Major**: significant composition drift, wrong hierarchy, unusable fill slot, transparency defect, or accessibility failure.
- **Minor**: small spacing, edge cleanup, or non-semantic visual mismatch.

Release requires zero blockers and zero majors. Minors must be fixed or explicitly accepted at G5.

## Repair ownership

Record each issue with slide/component ID, evidence image/path, severity, owner stage, repair attempt count, and disposition. If repairs occur, `qa-report.json.repairs` records each focused attempt with `slide_id`, `defect_class`, `owner_stage`, `artifact_path`, and attempt number 1–3. Repair the smallest owning artifact. Do not hide a defect by flattening the slide.
