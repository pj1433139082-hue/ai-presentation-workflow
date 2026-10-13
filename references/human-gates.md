# Human gates

> Scope: These G1–G5 and decomposition decisions govern the strict production/component-first route. Do not create these approvals for `showcase-v1` by implication; use [showcase-workflow.md](showcase-workflow.md) while retaining real human authority for consequential decisions and formal release.

For a user-authorized local project, record a short affirmative to the current complete packet with `approval_mode: local-affirmative`. The shared policy accepts common affirmative replies without asking for a prescribed echo; it rejects continuation, recommendation shortcuts in this mode, compound corrections, and ambiguous replies. G1 still needs the complete current authority packet and all critical decision/value bindings. Prior explicit approvals remain valid under their original rules; G5 accepts only its independent release mode and exact confirmation. Neither a populated state field nor validator success proves chat delivery or reply provenance.


If the user explicitly opts into low-friction local production, use the policy in `../SKILL.md`: accept a clear reply to the current packet without forcing an exact phrase, then continue reversible local trial/assembly with agent QA and honest reviewer labels. The strict gate and exact-phrase instructions below remain the default. Do not treat this mode as external-write or formal-release authorization.

Use five compact gates. Present decisions, tradeoffs, and representative visuals; do not send the human raw production noise.

## Presenting a gate and asking a question

At the **start** of every gate and each new review round, show a short stage card in the chat. The artifact packet may contain technical detail, but the chat message itself must state: (1) gate and current status; (2) what the user is deciding and why now; (3) exact artifact version, visible link(s), and the concrete evidence/conflict behind the question; (4) the recommended answer, its reason, and what another answer changes; (5) what approval permits next and what is still forbidden; and (6) the reply format. For a deck review, show the contact sheet and direct full-size page links, not just a packet filename. Separate a request to fix one page from approval of the whole gate. Do not ask for an approval while required evidence is still missing; say what is missing and ask only the independent decision that can be made now.

| Checkpoint | Tell the user what this checkpoint decides | Show before asking | Approval unlocks |
| --- | --- | --- | --- |
| G1 · scope and authority | Audience, decision goal, authoritative sources, fact/brand boundaries, search/generation permission, delivery, and exact editability promise | Inspected-source inventory, extracted facts, unresolved decision frontier, recommendation/impact per question | Story planning; not a license to invent facts or release |
| G2 · story | Slide order, action titles, one claim per page, evidence mapping, and appendix boundary | Storyboard, title-only narrative, missing evidence/claim risks | Visual reference study and design; not final copy approval |
| G3 · visual direction | Reference transfer, same-content image calibration, style strength/density, readable regions, stable font/frame meanings, then three anchors | 3–6 analyzed references, 2–3 comparable actual images, chosen variant and three full-content anchors with their limits | Expand full-deck contentful concepts; not component extraction |
| G4 · full-deck concepts | Exact visible copy/source/status, each full-size page, usable text/image space, cross-slide semantics and named exceptions | Numbered contact sheet **and every full-size page**, transcripts/source map, readability and semantic audits, unresolved defects | Textless master and numbered decomposition review; not asset production or final release |
| Post-G4 · decomposition | Which visible pieces must be independently movable and which regions remain native text/data, opaque photo, or fixed evidence | 100%-scale concept/master geometry comparison, each numbered page and item list, coverage/overlap/omission notes | Approved individual-asset work; not automatic batch PPTX production |
| Trial · one-slide PPTX | Whether independent assets can reconstruct one busy page with editable slots | Asset isolation sheets, actual one-slide PPTX render, 100%-scale side-by-side/overlay and deviations | Remaining-page assets and assembly after `确认单页试拼` in strict mode, or recorded agent QA in user-authorized low-friction local mode |
| G5 · release | Whether actual final deliverables and declared exceptions are acceptable | Rendered-PPTX contact sheet, every full-size concept/render comparison, per-page QA, exceptions and deliverable index | Release, only after `确认发布` |

Question delivery is a separate condition from gate approval. Use an available structured question tool according to its actual schema and mode, but never rely on a popup alone. In Codex Default mode, `request_user_input_async` returns immediately; its successful return means only that the request was submitted, **not** that a dialog appeared, was read, or was answered. In Plan mode, use synchronous `request_user_input` only when that tool is actually available; respect its question-count limit. If a tool cannot carry the complete current frontier, show the remaining questions in chat rather than silently dropping them. If the answer is required before work can proceed, repeat the full contextualized question and options in the **final response**, then wait for an actual user message. While continuing independent work, a visible commentary question may be used, but the next gate remains pending until the user answers. Do not put the only copy of a question inside an image, artifact, tool call, or earlier collapsed commentary.

Write each user-facing question as: “现在处于 [gate/status]，已有 [specific evidence/version]; [specific unresolved conflict] matters because [effect]. 我建议 [option]，因为 [reason]; 如果选 [other option]，会 [impact]. 请选择 [explicit options or free-form correction]. 回答后我会 [next action]; 在此之前不会 [blocked action].” Keep one decision per question and identify affected slide IDs where relevant. A tool-selected default, `accepted: true`, silence, `继续`, or an earlier `全部按推荐` is **not** an answer. Record a decision only after reading the user's actual reply and checking that the named artifact version/hashes are still current; if the reply changes copy or imagery, revise the owning artifact and re-present its new review packet. Never label an unobserved UI prompt as “已展示” or “已确认”.

The gate interaction loop is operational, not a wording checklist:

1. **Preflight.** Read the current `run-state.json`, gate artifact versions, and required evidence. Run the relevant validator; distinguish machine failures, intentionally pending human checks, and decisions the user can resolve now. A pending human judgment is the reason to ask when all inspectable evidence exists; a missing review image, source map, or other packet artifact is not. Do not request a whole-gate approval for an incomplete inspectable packet.
2. **Visible handoff.** Present the stage card and directly viewable evidence in chat. Keep the gate, packet version, slide IDs, and recommended value in the same message as the question or in the final blocking question. A file may carry detail, but may not be the only place where the user learns what they are approving.
3. **Scoped question.** Mark whether the reply will select a local option, approve a calibration candidate, approve the current whole gate, or authorize release. These are different scopes. An async UI request adds convenience but changes no workflow state.
4. **Receipt and reconciliation.** Use the user's actual reply, not tool submission status, as the receipt. Apply only its stated scope. A local correction, such as “按推荐” for one slide name, creates a new version of that slide and any dependent contact sheet/copy log; it does **not** approve the revised G4 deck. Re-run checks and re-present changed evidence. If the user says “继续” without answering a blocking choice, report the still-open choice and stop at that gate.
5. **Gate commit.** Only when the complete current packet has been shown and the reply explicitly covers that gate, save the approval phrase, reviewer, timestamp, version, decision values, and artifact hashes. Then run the gate validator again. If any bound artifact changed, the old approval is stale and the loop returns to handoff, not forward to the next stage.

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

The human sees the reference board, then 2–3 actual contentful concept images for the *same representative content slide* before the three anchors. Each image shows the verbatim approved title, concise visible copy realizing the approved narrative message, truth-status labels, and representative imagery. If the message is condensed, show its `message_mapping` and ask whether all meaning and truth boundaries survive; do not require the whole narrative sentence on-screen at the expense of readable text or image area. Keep the copy, evidence, visual intent, and remaining editable blank regions fixed; vary only a visible design direction and/or these two labeled axes: visual strength (`restrained`, `balanced`, `expressive`) and layout density (`airy`, `standard`, `dense`). The axes are not a forced 3×3 grid. Explain observable differences and tradeoffs, recommend one, and show the images side by side. A reference-board preference is provisional; do not treat gallery IDs, adjectives, or an automatically chosen theme as image-level approval.

Strength changes the prominence of color, scale contrast, material treatment, and visual metaphor; it must not add or remove claims. Density changes whitespace and module packing; it must not hide evidence or turn data into generated pixels. A useful default trio is restrained/airy, balanced/standard, and expressive/dense, but vary the pairing if it would confound a direction choice. Ask one concrete question: “以哪张概念图为基准？表现强度、版面密度是否要调一级？” Show what each adjustment would change.

Save the user's chosen variant in `run-state.json.gates.style_anchors.calibration_selection` with approver, time, version, the actual approval phrase, and SHA-256 hashes for `concept-calibration.json`, the comparison sheet, and all candidates. Use the existing explicit or batch rules in strict mode; authorized local mode also accepts a clear `local-affirmative` reply to the current selected-variant packet. If the user wants a hybrid or a changed degree, generate a new labeled candidate and ask them to select it; do not silently combine two images. `--stage style` must pass before proceeding to the three anchors. Only after this selection, generate the opening, typical, and hardest/highest-risk anchors with the selected direction, strength, and density. Then ask the human to approve the final G3 packet; the calibration choice is one of its decisions.

Approval packet: reference contact sheet and analysis, same-content contentful calibration comparison and selected variant, copy/source lineage and checked text evidence, chosen reference IDs, composition/richness and readability profiles, style contract, contentful anchor contact sheet, known image limitations, and the chosen direction. Check the actual image glyphs against the transcript and whether the real text/visual balance is readable; the presence of an OCR/transcript field alone is not an approval.

The saved G3 packet covers reference selection, concept calibration, composition and readability profiles, visual direction, observable style rules, the project-specific `semantic_system`, and the opening, typical, and highest-risk anchors. Explicitly align what repeated title/key-statement/qualifier treatments mean and what each verified, pending, or placeholder frame means before expanding the deck. A representative full-content slide must show those regions together; do not infer a semantic mapping from a style adjective.

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
- whether the same text-role ID has the same meaning, size, weight, color, and repeated-region purpose across pages; whether the same frame treatment has the same truth/status meaning and a visible label; and whether named cover/closing exceptions preserve those meanings

Approval packet: numbered contentful contact sheet, per-slide 100%-scale review image and readability record, per-slide version and copy/source map, hash-bound text-review transcripts/overlay evidence, source lineage, a short change list, a cross-slide semantic-role/frame audit, and a richness audit identifying any intentionally sparse pages. G4 includes `contentful_copy_source_review`, `full_deck_contact_sheet`, `readability_review`, and (for semantic-system v2 projects) `cross_slide_semantics_review`; all bind the current style, deck spec, copy log, and images. Component-master generation starts only after approval.

The saved G4 packet covers exact content and source lineage, the full-deck contentful contact sheet and image hashes, per-slide full-size readability and declared exceptions, slide-by-slide layout/richness review, blank table/chart regions, special-typography exceptions, and slide-specific deviations. Revisions use a new versioned image path and retain the previous one; a changed image, deck spec, or copy log invalidates the affected G4 approval.

## Post-G4 — decomposition confirmation before assets

After the current G4 approval and the 100%-scale contentful/textless-master geometry review, prepare `decomposition-map.json`. Render each slide's full-size numbered image and readable item list. Show the user both, including object boundaries, editable text/data slots, ordinary photos kept as one image, preserved/blank factual imagery, backgrounds, arrows/connectors, residual decorations and shadows, overlaps, and any deliberate omission. Ask the user to correct any missing object or pair that must move separately. Revise only the owning slide, regenerate that slide's review files, and keep historical images; do not reinterpret an old approval as approving a new version.

Page-local masters, geometry evidence, and decomposition drafts may be produced concurrently after G4; this does **not** create a user gate per page. The main agent merges them, presents one complete numbered packet, and requests one scoped decomposition decision. A worker's review or a page preview cannot approve the whole-deck gate. After the representative-page trial passes, other pages may produce components and one-page PPTX previews concurrently under the ownership rules in `page-parallel-production.md`; the final full-deck PPTX and G5 remain single-owner decisions.

The approval packet binds the current map version, concept and master hashes, every numbered image and readable list, and the user's semantic/residual coverage and independence decisions. Save it in `run-state.json.gates.decomposition` with `approval_mode: explicit` in strict mode or `local-affirmative` for a clear current scoped reply under authorized local mode; retain the actual approval phrase, approver, time, current `artifact_version`, decision values/hashes, and approved artifact hashes. This remains a human decision in both modes. Do not accept a prior `全部按推荐`, G4 approval, script PASS, or silence as decomposition approval. `--stage inventory` can be used to check the draft packet; `--stage assets` must fail until this gate is current. A rejection rolls back to `inventory` and clears only this gate's approval epoch; G4 remains approved unless the concept itself changes.

Programmatic checks can show whether every declared scene instance and fill slot has one mapping, whether two declared objects share an instance, and whether hashes are current. They cannot discover an object omitted from both the map and scene graph or judge whether a transparent image contains fused semantic objects. The human's full-size review carries that responsibility, and asset isolation is checked again after production.

## Post-decomposition — one-slide trial before batch

This gate is mandatory for production projects requesting PPTX; component-library-only work does not need to fabricate a PPTX.

Choose a representative content page with several independently movable objects, overlaps, and real text/main-image space. This is not the entire-deck G5 review. Complete and isolate only this page's assets, then prepare its approved contentful concept, every isolation sheet, actual one-slide PPTX render, 100%-scale side-by-side and overlay, and a short list of expected editable slots. Check fused or missing objects, obvious offsets, seams, color/layer drift, usable text/image regions, and factual labels. Present those checks to the human in strict mode; in user-authorized local mode record the agent's direct inspection. Do not fail on harmless texture differences alone.

The trial review starts pending. In strict mode only an explicit `确认单页试拼` for the current hash-bound packet can set `pilot-review.json.status: approved`. With the user's recorded low-friction local opt-in, the agent may set `status: agent-verified-local` after inspecting the actual render, comparison, isolation sheets, defects and repairs; name the agent reviewer and never call it human approval. Earlier `全部按推荐`, decomposition approval alone, script PASS, or a test fixture do not count. Rejected trials record component/page, evidence, severity, owner stage and local repair entry. Repair the smallest owning artifact; if the concept changes, create a new version and reapprove affected G4/decomposition decisions. Do not start remaining-slide asset production until `--stage pilot` passes.

## G5 — release

Ask the human to accept:

- final render/contact sheet
- declared differences from concept renders
- any unresolved OCR, accessibility, or fidelity exceptions
- component library and fill-slot usability
- editable PPTX behavior for a completed presentation project

Approval packet: final contact sheet, hash-bound QA summary (whole-deck and per-page checks/reviewers), exception register, and deliverable index.

Before asking for G5, show the reviewer the actual PPTX contact sheet and each 100%-scale concept/render comparison from `reviews/qa/<version>/`. Strict mode requires a recorded passed human visual review for every slide with current bindings. User-authorized low-friction local mode may use recorded agent page QA for a draft, keeping rejected or stale pages in draft. `finalize_deck_qa.py` is only a technical QA transition and cannot create the separate G5 approval.

G2–G4 use `approval_mode: explicit` with per-decision value hashes, or `approval_mode: batch-recommendations` with the exact phrase `全部按推荐`, visible recommendation reason and impact, and an accepted recommended value for every decision. User-authorized local mode also permits `approval_mode: local-affirmative` with a clear actual reply and the same complete current packet, decision values, and hashes. Every packet targets its gate and current version; every gate records the approved artifact paths and SHA-256 hashes.

G5 is different: use `approval_mode: release` and the exact independent phrase `确认发布`. Hash every presented release artifact, including the final contact sheet, QA evidence, exception register, and deliverable index. Never convert a G1–G4 approval, `全部按推荐`, or silence into release authority.

## Decision rule

Escalate when the choice changes meaning, brand, truth, or release acceptance. Do not escalate searchable facts, file naming, retry mechanics, or coordinate conversion.

When a gate is rejected or QA identifies a defect, record `rollback.trigger`, `reason`, `owner_stage`, and either `source_gate` or `defect_class`. A rejected gate must have a rollback record and must clear its prior approval version, packet, and artifact hashes before work resumes. Return only to the owning stage; keep unaffected earlier approvals intact. Changed artifacts invalidate only approvals whose saved hashes no longer match.
