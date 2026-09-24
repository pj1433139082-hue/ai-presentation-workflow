# Prompt patterns

These patterns adapt the structured, workflow-oriented ideas from [awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2): define modules and layout before style adjectives, keep module count controlled, use structured prompts, and make decorative typography an explicit single asset. If the local `gpt-image-2-style-library` skill or repository is installed, consult its relevant category/template/case and record the selected IDs in `style-contract.json`; do not copy the whole library into the project.

Use prompts as versioned data. Store the final prompt and references in the asset manifest.

## Full-slide concept

For production work, attach every selected project-local reference image used by this slide to the `image_gen` call. The prompt must identify reference IDs and extracted rules; never rely on a style name alone.

For calibration candidates, use the same structure below with identical approved `VISIBLE COPY`, `CONTENT ARCHITECTURE`, image truth/status classifications, and remaining blank fill slots for all 2–3 candidates. Change only `VISUAL SYSTEM`, reference grammar when directions call for it, and observable layout treatment. Save each exact prompt and show actual output images side by side. After the user selects one, record its variant ID, strength, and density in all anchor and full-deck concept prompts; do not infer a change from adjectives in chat.

```text
PURPOSE
Create one 16:9 contentful review concept for slide {slide_id}. It is for copy, imagery, and composition review only; it is never a final flattened slide.

MESSAGE
{single_message}

VISIBLE COPY — render every line exactly as supplied
- approved action title: {storyboard_title}
- concise on-slide copy and labels, with copy IDs and truth status: {copy_map}
- visible status labels: verified / planned / pending as mapped above
- do not translate, paraphrase, invent, omit, or respell any supplied text

STRUCTURE
- canvas: 16:9, safe margins {safe_margins}
- layout archetype: {layout_archetype}
- complexity: {sparse_standard_or_rich}
- modules, in reading order: {module_list}
- dominant module: {dominant_module}
- layout relationships: {layout_relationships}
- preserve blank fill slots only for content not included in VISIBLE COPY: {fill_slot_locations}

READABILITY AND DISPLAY SPACE
- approved per-slide text regions and planned point sizes: {readability_text_regions}
- usable main-image bbox, excluding decorative frame/glow: {main_visual_bbox}
- keep the action title at least 32 pt, ordinary body at least 20 pt, key captions at least 18 pt, and essential qualifiers at least 16 pt unless a named G4 exception is planned
- a readable evidence image gets at least 42% canvas width and 43% height; detailed full-interface UI prefers 50% width and 46% height, or a truthful focus crop
- if the supplied copy or real image cannot fit, simplify non-essential copy, enlarge/recompose, or split the slide; do not silently shrink text or evidence

CONTENT ARCHITECTURE
- information units: {information_units}
- visual layers: {visual_layers}
- variation from previous slide: {variation_from_previous}

REFERENCE GRAMMAR
- attached reference IDs: {reference_ids}
- transfer these rules: {transferable_rules}
- translate them for this deck as: {project_translation}
- do not copy: {do_not_copy_boundaries}
- use references for design grammar, not exact recreation

IMAGE TRUTH
- representative imagery and its class: {image_inventory}
- label illustrative imagery as illustrative; never let it imply verified product capability
- preserve verified source images unchanged, or use an explicit labeled placeholder when evidence is pending
- do not invent screenshots, interfaces, metrics, charts, or evidence

VISUAL SYSTEM
- direction: {style_direction}
- approved calibration variant: {selected_calibration_variant_id}
- visual strength: {restrained_balanced_or_expressive}
- layout density: {airy_standard_or_dense}
- palette: {palette}
- shape/material language: {shape_language}
- image treatment: {image_treatment}
- density and rhythm: {density}

CONTENT POLICY
- render the supplied approved ordinary copy for review; the final deck will keep ordinary text and data editable
- do not add any text outside VISIBLE COPY, except approved special typography: {allowed_exact_text_or_none}
- never encode unsupported facts as imagery or data marks

OUTPUT
One finished slide concept, clean edges, no mockup frame, no process sheet, no alternate versions, no watermark.
```

## Post-G4 textless component master

Generate this only after the current G4 approval. It preserves the approved full-slide geometry while removing ordinary text and data. It is a temporary decomposition master, not the final slide background.

```text
Using the G4-approved contentful concept for slide {slide_id}, create one textless component master.

PRESERVE
- canvas, composition, image placement, color, structure, visual layers, and approved special typography only
- keep the exact normalized geometry of every fill slot: {fill_slots}
- keep verified source images unchanged; keep pending items as the approved labeled placeholder

REMOVE
- all ordinary titles, body copy, labels, values, legends, citations, and data
- replace each removed text/data region with a clean blank fill slot at its approved location
- do not move, shrink, crop, or redesign neighboring elements to compensate

OUTPUT
One full-slide textless master for later inventory and component extraction. It is not a final deck slide, background, or substitute for transparent components.
```

Record the exact prompt plus every attached reference path and SHA-256 in the concept-generation log. A production concept without attached selected reference images is incomplete.

## Adapter-derived transparent component

This is the canonical pattern generated by the Material adapter. Do not accept a caller-written `{description}` or append arbitrary prose; the approved concept crop is the visual instruction.

```text
Using the approved full-slide concept and the local crop as visual references, regenerate exactly one isolated component.

TARGET
- role: {role}
- approved normalized crop: {reference_bbox}
- preserve: silhouette, orientation, palette, material, lighting, edge treatment, and relative detail

CANVAS
- fully transparent RGBA background
- generous transparent padding on every side
- target centered without cropping

EXCLUDE
- every neighboring object
- background scene, panel, frame, mockup, caption, watermark
- all text, letters, numbers, labels, and data
- checkerboard or white background pretending to be transparent

OUTPUT
One component only, production-ready transparent PNG, no variations or contact sheet.
```

## Table shell

```text
Regenerate only the table shell from the approved concept as one isolated transparent PNG.
Keep the outer frame, cell grid, border style, fills, blank header bands, corner treatment, and decorative accents.
Remove all text, letters, numbers, icons with labels, values, footnotes, and data marks. Leave every cell empty for later user input.
No surrounding slide background or neighboring objects. Fully transparent RGBA canvas with padding. One asset only.
```

## Chart shell

```text
Regenerate only the non-data chart shell from the approved concept as one isolated transparent PNG.
Keep the approved plot frame, empty axes or blank plotting region, structural grid style, container, and purely decorative accents.
Remove all values, tick labels, categories, legends, annotations, series labels, and every bar, line, point, area, or shape whose geometry communicates data.
No invented data. No surrounding slide background. Fully transparent RGBA canvas with padding. One asset only.
```

## Arrow or basic shape

```text
Regenerate exactly one {arrow_or_shape} from the approved concept.
Match its geometry, direction, stroke/edge language, color, material, and shadow treatment.
Isolate it on a fully transparent RGBA canvas with generous padding. No text, no labels, no other objects, no background, no alternate variants. One asset only.
```

## Special typography

```text
Create one finished decorative typography asset using this exact text: “{exact_text}”.
The wording, language, capitalization, and punctuation are locked. Do not add, omit, translate, or respell characters.
Typography is the sole hero object. Match the approved style: {typography_style}.
Fully transparent RGBA background, generous padding, no mockup, no poster layout, no unrelated symbols or secondary copy, no alternate versions.
```

After generation, OCR the result. A visually attractive misspelling is a failed asset.

## Focused repair

```text
Edit only component {component_id}. Keep all approved characteristics unchanged.
Correct this defect: {single_defect}.
Do not redesign, add objects, add text, alter orientation, or change the transparent canvas. Return one corrected transparent PNG.
```
