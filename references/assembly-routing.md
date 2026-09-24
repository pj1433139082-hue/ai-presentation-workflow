# Assembly routing

Choose exactly one presentation backend for a run.

## Use a PPTX backend when

- the user asks for a `.pptx` file;
- editable text/fill slots must exist in PowerPoint;
- speaker notes, slide size, or native placeholders matter.

Prefer the installed `presentations` runtime or the established `pptx` skill available in the environment. Inspect both, select one, and record the choice in `assembly-map.json`. Do not mix their internal helper implementations in one deck.

## Skip PPTX assembly when

- the user only wants transparent components and composition metadata;
- no compatible backend is available;
- the requested fidelity cannot be achieved without flattening the concept image.

In those cases, release the component library, scene graph, fill-slot map, contact sheet, and QA report. Do not fabricate editability.

## Assembly rules

- Concept images are references only and must not be placed as backgrounds.
- Place transparent PNGs by normalized scene-graph coordinates and z-order.
- Add editable placeholders for fill slots. Use clear temporary labels outside generated art.
- Keep source aspect ratio unless the scene graph explicitly records a crop.
- Update the scene graph when any placement is changed during assembly.
- Render the assembled deck for QA; do not judge only from object metadata.
- Describe editability honestly: PNG components are movable, scalable, crop-able, replaceable, and layerable, but their internal paths and colors are not native PowerPoint shapes.
