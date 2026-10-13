# Cross-slide semantic visual grammar

> Scope: Preserve meaning for semantic roles across all routes, but repeated coordinates and exact typography are project choices unless a brand/series contract requires them; `showcase-v1` may vary layout to fit the content.

Use this at G3 style calibration, S4 deck specification, G4 contentful-concept review, and final PPTX QA. It prevents the same font or frame treatment from changing meaning between pages. A coherent deck can still vary its central layout, imagery, and density.

## G3: agree on meanings before expanding the deck

Define `style-contract.json.semantic_system` for new production/draft projects. The project chooses its own values; do not hard-code a particular client's blue, font, or footer copy into the reusable skill.

- `text_roles`: stable IDs such as `action-title`, `key-takeaway`, `status-qualifier`, `module-heading`, `body`, and `metric`. Each declares one semantic `meaning`, a readability `role`, native-PPT `font_family`, exact `font_size_pt`, `bold`, and `color`. The same ID has one treatment throughout the deck. Size alone must not encode verified vs pending.
- `frame_roles`: stable IDs with one `meaning`, `line_style` (`solid`, `dashed`, or `none`), `color` when a line exists, and `visible_label_required`. If a solid frame means verified and a dashed frame means pending, that mapping is deck-wide; an empty evidence placeholder uses a different role and must not look like verified evidence. Truth status must also be written in words.
- `repeated_regions`: the semantic role and approximate `[x,y]` anchor for repeated areas such as page title, key takeaway, and truth/status qualifier. Decide whether each is required. A cover or closing page can change the anchor only through a named page exception with a reason; it does not silently change the type token's meaning or size.
- Explicitly say what accent colors mean. An attention color or flow arrow is not evidence status unless the style contract says so and the slide also has a visible status label.

Show the user a representative contentful slide with the complete title, middle content, and bottom key statement before applying the grammar to the entire deck. G3 approval covers the role meanings and representative treatment; G4 still approves the exact nine-page realization. A response approving an earlier G4 packet does not approve a changed semantic system.

## S4 and concept generation: bind every use

In `deck-spec.json.slides[*]`:

- Every ordinary `readability.text_regions[*]` uses `font_role` to reference a declared `text_roles` ID. Its `planned_font_pt` equals that token's exact size; `role` equals the token's readability role. Ordinary copy remains an editable fill slot.
- `semantic_design.region_slots` maps every required repeated region to its fill-slot ID. Keep title and key-statement copy source-mapped; don't invent a conclusion merely to fill a footer.
- `semantic_design.frame_instances` lists each meaningful frame with `id`, `role`, normalized `bbox`, and a visible `label_slot_id` when the role requires one. A decorative line need not be a status frame, but it must not mimic a declared status treatment.
- `semantic_design.exceptions` lists only anchor deviations, each with `region_id` and concrete `reason`. A required repeated region cannot disappear through an exception. Exceptions cannot waive text-size, truth-label, or evidence-area floors.

Pass the same approved semantic-system record and this slide's bindings into every contentful-concept prompt. The prompt should explicitly distinguish the title, takeaway, qualifier, module heading, source note, verified frame, pending frame, and blank evidence pane; do not ask `image_gen` to decide their meanings independently on each page. Generated bitmap text is an approximation for G4 review, not proof of exact pt sizes. Use native text and asset assembly later.

If long titles or real images collide with repeated bands, first shorten *non-essential* visible copy without changing the approved claim, reflow modules, use a truthful crop, or split a slide. Do not silently shrink a text role or the usable evidence pane. A two-line title may grow its container while retaining the same token and anchor. Check the inner evidence pane, not its decorative outer frame.

## G4 and QA: review both the sheet and the full-size pages

The G4 packet includes a cross-slide semantic audit: for each repeated region, compare position, role, size intention, copy purpose, and allowed exceptions; for each frame role, compare meaning, visible label, and truth status. Show a contact sheet for cross-page rhythm plus every page at 100% for text, labels, and actual image area. A page can pass local readability yet fail because its typography or frame meaning disagrees with the rest of the deck.

The assembler should apply `text_roles` to native PowerPoint text and the validator should compare the PPTX font family, size, weight, and color with those tokens. In final QA, compare actual PPTX renders and inspect frame semantics visually; metadata cannot prove that a generated image's border is the declared solid/dashed treatment. A semantic mismatch is a G3 style defect if the mapping is wrong, a G4 concept defect if one page violates the mapping, or an assembly/asset defect if the final output drifts from an approved concept.

For projects started before this contract existed, do not mutate a hash-approved G3 style file in place. Prepare a versioned style amendment and representative page, obtain the relevant human alignment, then rebind affected G3/G4 approvals. The validator accepts legacy projects without `contract_schema_version: 2`; new templates use version 2 and require `semantic_system`.
