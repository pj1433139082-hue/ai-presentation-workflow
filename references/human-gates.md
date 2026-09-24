# Human gates

Use five compact gates. Present decisions, tradeoffs, and representative visuals; do not send the human raw production noise.

## G1 — brief and authority

First inspect the supplied material. Record inspected paths and hashes, facts that can be extracted, unresolved decisions, and the current question frontier in `alignment.json`. Do not ask the human to repeat a discovered fact.

The following decisions are consequential and must be resolved before Story:

- audience and decision goal
- delivery form and acceptable editability
- editability level: native text/data, component-level raster manipulation, internal vector/path editing, and native chart/table behavior are different promises
- source-of-truth documents and research boundary
- facts, figures, screenshots, equations, or brand assets that must remain exact
- permission boundaries for external search, image generation, and optional PPTX creation
- component/call budget, deadline fallback, and acceptable visual approximation from reference-guided regeneration

Approval packet: one-page brief, source inventory, known gaps, and assumptions with impact.

Ask only the current frontier: use the first five independent unresolved decisions in ledger order, or all of them when fewer than five are available. When at least three are available, never ask fewer than three. Each question shows a recommended answer, why it is recommended, and what changes if the user chooses differently. Dependent questions wait for the next round. File naming, retries, coordinate conversion, and similar mechanics use agent defaults and never block G1.

An explicit answer may approve decisions individually. Save a `decision_approvals` record for every consequential decision with the SHA-256 of its canonical approved value. The exact phrase `全部按推荐` may approve the whole G1 packet only when every consequential decision and recommendation is visible in that packet. Save `approval_mode`, the exact `approval_phrase`, approver, time, artifact version, and SHA-256 hashes for `brief.json`, `alignment.json`, and `research-bundle.json`. `按推荐`, a batch phrase mislabeled as explicit approval, silence, inferred intent, or a hash/version mismatch does not approve G1.

## G2 — story

Ask the human to approve:

- slide sequence
- action titles
- one message per slide
- evidence-to-slide mapping
- which details move to appendix

Approval packet: storyboard table plus title-only narrative. Do not design all slides before this gate.

The saved G2 packet covers slide sequence, action titles, slide messages, evidence mapping, and appendix boundary.

## G3 — visual direction and anchors

Before generating concepts, show a numbered board of 3–6 analyzed references for production work. Every reference states what transfers into the project and what must not be copied. Offer two or three concrete directions derived from that board, then recommend one. For each, show observable differences in structure, palette, typography intent, density, imagery, layout archetypes, and content/visual-layer thresholds.

The human sees the reference board, then 2–3 actual contentful concept images for the *same representative content slide* before the three anchors. Each image shows the approved title and message, visible truth-status labels, and representative imagery. Keep the copy, evidence, visual intent, and remaining editable blank regions fixed; vary only a visible design direction and/or these two labeled axes: visual strength (`restrained`, `balanced`, `expressive`) and layout density (`airy`, `standard`, `dense`). The axes are not a forced 3×3 grid. Explain observable differences and tradeoffs, recommend one, and show the images side by side. A reference-board preference is provisional; do not treat gallery IDs, adjectives, or an automatically chosen theme as image-level approval.

Strength changes the prominence of color, scale contrast, material treatment, and visual metaphor; it must not add or remove claims. Density changes whitespace and module packing; it must not hide evidence or turn data into generated pixels. A useful default trio is restrained/airy, balanced/standard, and expressive/dense, but vary the pairing if it would confound a direction choice. Ask one concrete question: “以哪张概念图为基准？表现强度、版面密度是否要调一级？” Show what each adjustment would change.

Save the user's chosen variant in `run-state.json.gates.style_anchors.calibration_selection` with approver, time, version, exact phrase, and SHA-256 hashes for `concept-calibration.json`, the comparison sheet, and all candidates. If the user wants a hybrid or a changed degree, generate a new labeled candidate and ask them to select it; do not silently combine two images. `--stage style` must pass before proceeding to the three anchors. Only after this selection, generate the opening, typical, and hardest/highest-risk anchors with the selected direction, strength, and density. Then ask the human to approve the final G3 packet; the calibration choice is one of its decisions.

Approval packet: reference contact sheet and analysis, same-content contentful calibration comparison and selected variant, copy/source lineage and checked text evidence, chosen reference IDs, composition/richness and readability profiles, style contract, contentful anchor contact sheet, known image limitations, and the chosen direction. Check the actual image glyphs against the transcript and whether the real text/visual balance is readable; the presence of an OCR/transcript field alone is not an approval.

The saved G3 packet covers reference selection, concept calibration, composition and readability profiles, visual direction, observable style rules, and the opening, typical, and highest-risk anchors.

## G4 — concept contact sheet

Ask the human to approve the entire deck at thumbnail/contact-sheet scale **and each contentful slide at 100% size** for checking exact copy, truth labels, imagery, and readable display regions:

- composition rhythm and hierarchy
- repeated motifs
- consistency across sections
- slide-specific exceptions
- whether special typography should be image-based
- which table/chart regions must remain blank
- whether ordinary content pages have enough meaningful information units and visual layers
- whether the deck varies layout archetypes without becoming inconsistent
- whether every displayed title/body/status label matches its copy map and the source lineage supports each claim
- whether illustrative images are labeled as illustrative, verified source images remain exact, and pending evidence stays a placeholder
- whether the actual title/body copy fits its declared point size and every main evidence image is usable at the approved inner-pane bbox; inspect each underfloor exception and its alternative viewing route

Approval packet: numbered contentful contact sheet, per-slide 100%-scale review image and readability record, per-slide version and copy/source map, hash-bound text-review transcripts/overlay evidence, source lineage, a short change list, and a richness audit identifying any intentionally sparse pages. G4 includes `contentful_copy_source_review`, `full_deck_contact_sheet`, and `readability_review`; all bind the current deck spec, copy log, and images. Component-master generation starts only after approval.

The saved G4 packet covers exact content and source lineage, the full-deck contentful contact sheet and image hashes, per-slide full-size readability and declared exceptions, slide-by-slide layout/richness review, blank table/chart regions, special-typography exceptions, and slide-specific deviations. Revisions use a new versioned image path and retain the previous one; a changed image, deck spec, or copy log invalidates the affected G4 approval.

## G5 — release

Ask the human to accept:

- final render/contact sheet
- declared differences from concept renders
- any unresolved OCR, accessibility, or fidelity exceptions
- component library and fill-slot usability
- optional PPTX behavior

Approval packet: final contact sheet, QA summary, exception register, and deliverable index.

G2–G4 use `approval_mode: explicit` with per-decision value hashes, or `approval_mode: batch-recommendations` with the exact phrase `全部按推荐`, visible recommendation reason and impact, and an accepted recommended value for every decision. Every packet targets its gate and current version; every gate records the approved artifact paths and SHA-256 hashes.

G5 is different: use `approval_mode: release` and the exact independent phrase `确认发布`. Hash every presented release artifact, including the final contact sheet, QA evidence, exception register, and deliverable index. Never convert a G1–G4 approval, `全部按推荐`, or silence into release authority.

## Decision rule

Escalate when the choice changes meaning, brand, truth, or release acceptance. Do not escalate searchable facts, file naming, retry mechanics, or coordinate conversion.

When a gate is rejected or QA identifies a defect, record `rollback.trigger`, `reason`, `owner_stage`, and either `source_gate` or `defect_class`. A rejected gate must have a rollback record and must clear its prior approval version, packet, and artifact hashes before work resumes. Return only to the owning stage; keep unaffected earlier approvals intact. Changed artifacts invalidate only approvals whose saved hashes no longer match.
