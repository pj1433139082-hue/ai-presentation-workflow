# Reference-first design and production richness

Use this contract before generating the first concept image. References are design evidence, not decoration and not permission to copy a finished work.

## Reference study

Create `reference-study.json` during Style. For a production deck, curate 3–6 relevant visual references from user-supplied material, the local `awesome-gpt-image-2` library, approved provider examples, or opened original web sources. Prefer references that solve the same communication problem rather than references that merely share a color palette.

Every selected reference needs a project-local image, SHA-256, original locator, usage note, and an analysis covering:

- composition and reading order;
- hierarchy and focal point;
- density and whitespace;
- image/material treatment;
- transferable rules;
- translation into this deck;
- explicit `do_not_copy` boundaries;
- target slide roles.

Reference lifecycle is `captured → analyzed → selected`; a URL, gallery ID, or attractive image alone is only `captured`. Never label it analyzed without observations, transfer rules, project translation, and do-not-copy boundaries.

Create a numbered reference contact sheet and present 2–3 direction options. Each direction cites the references it draws from and states structure, palette, density, imagery, and tradeoffs. These are hypotheses, not the final visual choice. The selected reference IDs enter the G3 packet.

## Same-content concept calibration

Before the three anchors, choose one representative storyboard slide and create `concept-calibration.json`. Use Codex `image_gen` to make 2–3 real 16:9 concept images. Hold the slide's title, message, evidence IDs, visual intent, and blank editable regions constant. Label each candidate's `direction_id`, `style_strength` (`restrained` / `balanced` / `expressive`), and `layout_density` (`airy` / `standard` / `dense`). Describe the actual difference in hierarchy, layering, whitespace, material, and image treatment; the labels alone do not establish variety. This comparison should help the user choose how strongly designed and how dense the deck should feel, not choose between different arguments.

Record the exact prompt, attached local reference images and hashes, tool/model, output file/hash, a contact sheet, recommended candidate, reason, and impact. Show the real images side by side. The human may pick a candidate, reject all, or request a hybrid; a hybrid is a new candidate to generate and review. Save a hash-bound `calibration_selection` approval before producing anchors. The final style contract records the selected candidate ID, direction ID, strength, and density. The three anchors and every later concept inherit that selection. G4 remains a separate review of the whole deck's visual rhythm.

For `awesome-gpt-image-2`, consult only relevant categories/templates/cases. Record the repository-relative category, template, or case ID and copy only the selected preview into the project. Do not import the whole gallery or reuse case copy, logos, characters, or a distinctive finished composition.

## Concept generation

Production concepts use `image-and-analysis` reference mode:

1. Pass the selected project-local images to Codex `image_gen` as reference images, and apply the human-selected calibration variant's direction, strength, and density.
2. Include the extracted transferable rules, project translation, and do-not-copy boundaries in the structured prompt.
3. Combine those references with the approved storyboard, fill slots, layout archetype, information units, and visual layers.
4. Record exact prompt text, reference paths/hashes, model/tool identity, and output hash.

References guide design grammar. They never override truth, brand, editability, blank table/chart regions, or the prohibition on baked ordinary text/data.

## Quality profiles

`brief.json.quality_profile` is one of:

- `production`: real deliverable; reference-first and richness checks are mandatory.
- `draft`: exploratory deliverable; references and composition planning remain required, but thresholds may be lower.
- `validation-fixture`: contract/tool test only; it must also set `run-state.json.fixture_only: true` and must never be presented as a production-quality deck.

The default is `production`. Do not silently downgrade because the run is automated or time-boxed.

## Production richness

Richness means structured communication, not ornament count. `style-contract.json.composition_profile` fixes the approved thresholds. The recommended production baseline is:

- `visual_richness: balanced-rich`;
- at least 3 layout archetypes when the deck has enough slides;
- no more than 2 consecutive slides using the same archetype;
- at least 3 information units on an ordinary content slide;
- at least 2 visual layers on an ordinary content slide;
- sparse layouts limited to opening, transition, and closing roles.

An information unit is a meaningful claim, evidence item, mechanism step, comparison dimension, decision, or action. Titles, footers, page numbers, and decorative labels do not count.

A visual layer is a distinct communication layer such as a main illustration, diagram, chart/table shell, process connector system, evidence image, annotation layer, or structural field. Background color and purely decorative noise do not count.

Each `deck-spec.json` slide declares:

- `layout_archetype`;
- `complexity`: `sparse`, `standard`, or `rich`;
- `information_units` with stable IDs and roles;
- `visual_layers` with stable IDs and roles;
- `reference_ids` used for that slide;
- `variation_from_previous` after the first slide.

Do not satisfy the contract by splitting one idea into fake units or counting shadows, dots, and background shapes as layers. G4 and QA inspect the rendered result, not just the JSON counts.

Useful archetypes include asymmetric hero, process journey, system map, comparison, evidence/data, timeline, matrix, case study, before/after, roadmap, and decision/next-step. Choose them from the story; do not rotate layouts mechanically.

Unless the approved direction explicitly requires a restrained minimal system, a production deck of five or more slides should contain at least one `rich` content slide. Minimal direction is still production work: it needs meaningful hierarchy, evidence, and intentional variation rather than empty space caused by missing content.

## Resuming an older project

If a project predates `quality_profile`, `reference-study.json`, or the composition fields, preserve its files and approvals as historical versions. Add the missing artifacts to a new version, then show the new reference board and composition profile at G3. Changes to the style contract, anchor images, deck spec, or concept images invalidate only the approvals bound to those changed hashes; request fresh G3/G4 approval before continuing. Do not relabel an old test deck as production or silently upgrade an approved artifact in place.
