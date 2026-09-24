# Readability and display regions

Use this contract while planning a production/draft slide, while reviewing its **contentful** concept at G4, and again after PPTX assembly. A thumbnail contact sheet tests deck rhythm; it does not prove projected readability. Review every slide at native/full-slide size with the actual approved copy and representative image or truth-sensitive placeholder visible.

## Default 16:9 planning profile

These are minimum planning guardrails, not a guarantee for every room or projector. Record a project-specific `readability_profile` in the style contract and an explicit `readability` record for each slide in the deck spec.

| On-slide role | Default minimum |
| --- | ---: |
| Action title | 32 pt (aim for 32–40 pt) |
| Ordinary body | 20 pt (aim for 20–24 pt) |
| Key status / caption | 18 pt |
| Essential source qualifier | 16 pt |

A primary screenshot or evidence image that must be read should normally reserve at least 42% of slide width **and** 43% of slide height. Measure the **usable flat content pane**, not its decorative frame, glow, or shadow. Fine interface detail should preferentially have 50% width and 46% height, or use a truthful crop and callout. Two compared views may each use narrower frames only when each still communicates its intended detail; do not shrink two full interfaces to show that there are two. The main illustrative image on a non-evidence slide needs an intentional visual area, but do not apply the evidence threshold mechanically to a small decorative icon.

## Per-slide record

In `deck-spec.json.slides[*].readability`, declare:

- `text_regions`: each visible ordinary text region names its `fill_slot_id`, `role` (`action-title`, `body`, `key-caption`, `source-qualifier`), `planned_font_pt`, and expected `line_count`. The referenced fill slot supplies the normalized bbox. Compare the actual approved copy with that bbox at full size; merely declaring a compliant point size does not prove the words fit.
- `main_visual`: `kind` (`evidence`, `fine-ui`, `illustration`, or `not-applicable`), a normalized bbox for the meaningful, usable primary visual, and an explanation when not applicable. An `evidence`/`fine-ui` bbox must equal the actual `fixed-evidence` fill-slot bbox, not an invented larger decorative frame. A `fine-ui` visual declares `detail_mode: full-interface` or `focus-crop`; the former uses the larger preferred frame, while the latter still meets the evidence baseline. For factual images, record whether the contentful concept shows the original unchanged or a visibly labeled placeholder.
- `exception`: normally null. A deviation lists precise failing floor IDs (`font:<fill_slot_id>` or `visual:main`), its reason, and an `alternative_viewing_route` (larger crop, live demo, notes, or extra slide). Do not use a generic “design choice” exception. It becomes approved only when the current G4 `readability_review` decision binds it.
- `full_size_review`: a separate per-slide evidence path/hash or the native-size contentful image path/hash, `status: passed`, `display_scale_percent: 100`, reviewer, and the exact `reviewed_concept_sha256`. The path/hash is added only after the image exists; a stale image requires fresh review. The G4 packet presents these images at 100% scale, not only in a contact sheet.

The public validator checks the declared minimum font sizes, region geometry, exception completeness, and links to the current concept/G4 approval. It does **not** claim to infer visual legibility solely from metadata. G4 must show the full-size render and resolve cropping, crowding, or contrast defects by actual inspection. G5 checks the assembled render and actual native text/image placement again. The textless component master must preserve the approved text and visual fill-slot bboxes; otherwise the readable concept did not survive decomposition.

## Repair order

1. Cut or rewrite non-essential on-slide copy; move detail to speaker notes or appendix.
2. Enlarge the main image or use a truthful key-area crop with a separately labeled detail view.
3. Change the layout or split the argument across slides when the speaking time allows.
4. Only if a real constraint remains, request an explicit per-slide exception at G4. Never auto-shrink text or evidence into a tiny frame to make the page fit.

The review applies to both text and pictures. An attractive slide with a large decorative wave but a tiny source screenshot is still unreadable.
