# Prompt patterns

These patterns selectively adapt [awesome-gpt-image-2](https://github.com/freestylefly/awesome-gpt-image-2/tree/5cb9109ca2d29476f8e34dbc0cdb43607bdd3f77): name the artifact first, define modules and relationships before styling, and describe materials through visible properties. Gallery prompts are design examples, not evidence of factual accuracy or reliable model behavior. Use the available Codex `image_gen` tool; the repository's model name does not select a runtime model. If a local copy is available, consult its relevant category/template/case and record the selected IDs in `style-contract.json`; do not copy the whole library into the project.

Use prompts as versioned data. Store the final prompt and references in the asset manifest.

## Select a pattern by the slide's job

Match the approved narrative/page role to a layout pattern before choosing visual tags. Usually 3–5 major modules are a useful starting point for a normal information slide; the approved storyboard and readability budget decide the actual count. A gallery's vertical poster, 17-section encyclopedia or seven-scale atlas needs recomposition or multiple slides, not smaller type.

| Slide job | Source pattern, checked against case content | Transfer into this workflow |
| --- | --- | --- |
| Explain a process or mechanism | `infographic-engine`; case 407, Neuro-AI system | One focal object plus a short ordered chain; name every connector's origin, destination and meaning. Use only approved mechanisms and claims. |
| Explain features around a subject | Case 222, modular encyclopedia; case 494, electric-bus engineering | One dominant subject, a few genuine detail views and grouped callouts. Omit automatic specifications, scores, dashboards and made-up capabilities. |
| Explain changes of scale | `scientific-scale-diagram`; case 380, coronavirus scale sequence | Distinct views in a declared order; use supplied source images and source-backed units. Missing scales stay pending; never ask the model to auto-discover scientific facts. |
| Keep a deck visually coherent | Case 453, enterprise brochure | Repeat title hierarchy, palette, spacing and material language while varying page composition. Build the overview from actual rendered pages rather than generating a pretend finished deck. |
| Create explicitly approved decorative type | `poster-layout-system`; case 355, conceptual typography | One exact phrase as one isolated hero asset; no optional micro-copy, portraits or catalog text unless separately part of the approved scope. |

Source: [template document](https://github.com/freestylefly/awesome-gpt-image-2/blob/5cb9109ca2d29476f8e34dbc0cdb43607bdd3f77/docs/templates.md), [case records](https://github.com/freestylefly/awesome-gpt-image-2/blob/5cb9109ca2d29476f8e34dbc0cdb43607bdd3f77/data/cases.json). At this snapshot some `style-library.json.exampleCases` entries point to different subjects: for example, its scale template lists case 341, whose actual record is a calculus study sheet. Verify the case's title, prompt and image before citing it; case 380 is the scale-sequence example used here. Cases 222, 380 and 453 were also visually inspected; the other transfers above are based on prompt text.

Compile the selected pattern into the existing concept template; it is not an extra output or approval stage:

- **Name the target and count.** State one review concept, one component, or one repair. Name the focal subject and exact approved module count; do not request a main and backup design inside one image. Calibration variants remain separate comparable images.
- **Assign reference roles.** Identify which attached image supplies layout, which supplies surface/edge language, and which is preserved factual content. A gallery is never an evidence reference. When references disagree, use the approved contract; unresolved conflicts return to the relevant existing decision stage.
- **Make style observable.** Replace adjective piles with medium, surface, edge, perspective and light: for example, matte flat fills, a thin consistent outline, restrained grain, and no cast shadow. For a 3D component, specify roughness, highlight width, light direction and camera angle only when supported by the chosen reference. Do not add glow or plastic gloss to every style.
- **Control copy before detail.** Use approved short lines and their IDs, not generated paragraphs or automatic facts. Define the dominant region, label regions, reading order and unused space before decorative detail. Exact visible copy includes qualifiers and pending labels.
- **Order the constraints.** Source truth and exact approved copy, then approved structure and geometry, then style and decoration. If these cannot fit together, recompose or split through the existing workflow; never silently trade away evidence or qualifiers.

Write free-form concept and repair prompts in the user's language unless they ask otherwise. Fixed adapter prompts retain their recorded language/version for reproducibility. Do not translate a canonical component prompt after planning; store and use the exact emitted text.

## Full-slide concept

For production work, attach every selected project-local reference image used by this slide to the `image_gen` call. The prompt must identify reference IDs and extracted rules; never rely on a style name alone.

Resolve contradictions between copy, source imagery, geometry and the selected style before calling `image_gen`, through the relevant existing decision stage. The prompt sent to the image model contains the resolved visual instructions.

For calibration candidates, use the same structure below with identical approved `VISIBLE COPY`, `CONTENT ARCHITECTURE`, image truth/status classifications, and remaining blank fill slots for all 2–3 candidates. Change only `VISUAL SYSTEM`, reference grammar when directions call for it, and observable layout treatment. Save each exact prompt and show actual output images side by side. After the user selects one, record its variant ID, strength, and density in all anchor and full-deck concept prompts; do not infer a change from adjectives in chat.

```text
PURPOSE
Create one 16:9 contentful review concept for slide {slide_id}. It is for copy, imagery, and composition review only; it is never a final flattened slide.

NARRATIVE MESSAGE — semantic constraint, not necessarily literal on-slide text
{single_message}
If realized by concise visible copy, preserve every claim and status boundary per {message_mapping}; do not force the entire narrative sentence into the image.

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
- each connector's source, destination and meaning, or none: {connector_bindings}
- subject viewpoint, relative scale and reserved copy regions: {subject_and_copy_geometry}
- preserve blank fill slots only for content not included in VISIBLE COPY: {fill_slot_locations}

READABILITY AND DISPLAY SPACE
- approved per-slide text regions and planned point sizes: {readability_text_regions}
- usable main-image bbox, excluding decorative frame/glow: {main_visual_bbox}
- keep the action title at least 32 pt, ordinary body at least 20 pt, key captions at least 18 pt, and essential qualifiers at least 16 pt unless a named G4 exception is planned
- a readable evidence image gets at least 42% canvas width and 43% height; detailed full-interface UI prefers 50% width and 46% height, or a truthful focus crop
- if the supplied copy or real image cannot fit, simplify non-essential copy, enlarge/recompose, or split the slide; do not silently shrink text or evidence

CROSS-SLIDE SEMANTIC GRAMMAR
- approved text-role IDs, meanings, native type tokens, and repeated title/key-message/qualifier anchors: {semantic_system_text_and_regions}
- this slide's exact text-role/fill-slot bindings and named anchor exceptions: {semantic_design_region_slots_and_exceptions}
- approved frame-role meanings and solid/dashed/blank treatments, including visible truth labels: {semantic_system_frames_and_slide_instances}
- an evidence placeholder is an empty image/data slot, not verified evidence: keep its declared no-status-border treatment even when neighboring verified cards have cobalt solid outlines; never copy a verified border or corner bracket onto the empty slot
- distinguish ordinary module-card grouping from truth/status frames by the approved line weight, color and explicit status label; a generic card must not accidentally look like an unlabeled verified frame
- keep these meanings and type hierarchy identical across the deck; vary the middle composition, not the semantic code

CONTENT ARCHITECTURE
- information units: {information_units}
- visual layers: {visual_layers}
- variation from previous slide: {variation_from_previous}

REFERENCE GRAMMAR
- attached reference IDs: {reference_ids}
- role of each attachment — layout, appearance, or preserved factual content: {reference_roles}
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
- observable medium, surface/edge treatment, viewpoint and lighting, or flat graphic with no physical lighting: {material_and_light_tokens}
- image treatment: {image_treatment}
- density and rhythm: {density}

CONTENT POLICY
- render the supplied approved ordinary copy for review; the final deck will keep ordinary text and data editable
- do not add any text outside VISIBLE COPY, except approved special typography: {allowed_exact_text_or_none}
- never encode unsupported facts as imagery or data marks

OUTPUT
One finished slide concept, clean edges, no mockup frame, no process sheet, no alternate versions, no watermark.
```

### Chinese composition example

This is a layout example for an explicitly illustrative, unverified proposal. Replace its copy, geometry and reference IDs from the current project; it does not establish an approval or replace the complete concept template above.

```text
产物：S03 的一张 16:9 审阅概念图。用途是评审拟议流程的版式。
固定文案：标题“拟议数据检查流程”；节点“采集”“检查”“反馈”；限定语“方案示意，尚未验证”。逐字保留，不添加英文副标题、编号、指标或额外说明。
结构：三个节点从左到右排列，采集指向检查，检查指向反馈；箭头只表示处理顺序，不表示已经运行或验收。检查节点略大，成为主视觉；标题和底部限定语各留独立可读区域。
参考分工：附图 R01 提供横向分组和留白规则，R02 提供扁平填色与细线边缘。只迁移这些规则，主题图像和事实来自本项目；不复制参考图里的品牌、文案或数据。
视觉：采用当前选定校准方案的米白背景、深蓝主体色和青绿强调色。使用哑光平面色块、统一细描边，无立体高光；装饰留在节点外侧，不侵占文字区域。
可读性：遵守本页已规划的字号和安全边距；信息过多时减少装饰或回到分页面方案，不压缩限定语。
输出：一张完整概念图。普通文字在最终 PPT 中以可编辑文本重建，节点和箭头分别生产组件。
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

New Material adapter plans emit structured `prompt_profile: v6` prompts, with a role-specific instruction for each object. Use the exact emitted prompt; the block below explains its intent rather than providing another freely editable prompt. Do not accept a caller-written `{description}` or append arbitrary prose; the approved concept crop is the visual instruction. Existing manifests without `prompt_profile` continue to validate against the unchanged `v1` prompt. Replanning with a newer profile is explicit in the resulting record and does not revalidate an existing image automatically.

```text
Using the approved full-slide concept and the local crop as visual references, regenerate exactly one isolated component.

TARGET
- role: {role}
- approved normalized crop: {reference_bbox}
- preserve: silhouette, orientation, palette, material, lighting, edge treatment, and relative detail
- keep the object's own proportions; do not stretch it to match the output canvas
- panel/node: empty outer body; table/chart: empty non-data shell; arrow: its exact path and heads; illustration/icon: constituent parts belonging to that one object

CANVAS
- fully transparent RGBA background
- generous transparent padding on every side
- target centered without cropping
- preserve intentional opaque interior fills; only the surrounding canvas must be transparent

EXCLUDE
- every neighboring object
- background scene, unrelated panels/frames, mockup, caption, watermark
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

Supply the failed component as the base image and identify the approved appearance reference separately, when one is needed. List the immutable characteristics and one observable defect, not a broad request to make it more polished. If the fix needs several changes, separate them into named bounded attempts and record each result; stop and inspect when the same defect persists rather than repeatedly enlarging the prompt.

```text
Edit base image {base_image_id}, component {component_id}; approved appearance reference: {reference_id_or_none}.
Keep these characteristics unchanged: {approved_invariants}.
Correct only this observable defect in this region: {single_defect_and_region}.
The result passes when: {visual_acceptance_condition}.
Preserve the canvas size, real alpha, object proportions and approved ordinary-text/data exclusions. Do not add neighboring objects or redesign unaffected regions. Return one corrected transparent PNG.
```

If the approved recipe calls for source-bound cropping, deterministic alpha correction, or native PPT text repair, perform that operation rather than generative repainting. A screenshot, data figure or other factual source always follows its preservation route; this component repair pattern does not authorize editing it.
