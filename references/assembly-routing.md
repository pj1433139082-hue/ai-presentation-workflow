# Assembly routing

> Scope: The picture-per-scene assembly rules below are for the legacy component-first route. A `showcase-v1` hybrid object contract may use native text, geometry, tables, or charts only when its current backend has verified them; see [hybrid-object-design.md](hybrid-object-design.md).

Choose exactly one presentation backend for a run.

## Use a PPTX backend when

- the project uses the default completed-presentation scope or the user asks for a `.pptx` file;
- editable text/fill slots must exist in PowerPoint;
- speaker notes, slide size, or native placeholders matter.

Prefer the installed `presentations` runtime or the established `pptx` skill available in the environment. Inspect both, select one, and record the choice in `assembly-map.json`. Do not mix their internal helper implementations in one deck. The current `assemble_editable_pptx.py` implementation uses the installed `python-pptx` backend and PowerPoint rendering on Windows; if those capabilities are unavailable, the run must select and verify another backend rather than claiming this one worked.

## Component-only exception

- the user explicitly asks only for transparent components and composition metadata.

If the user explicitly asks for components only, hand off the component library, scene graph, fill-slot map, contact sheet, and QA report as a component-only result. It is not a completed three-folder presentation project. If a compatible backend is unavailable or editability cannot be achieved without flattening, keep the PPTX project blocked or clearly draft; do not claim the final handoff complete or fabricate editability.

## Assembly rules

- Concept images are references only and must not be placed as backgrounds.
- Place transparent PNGs by normalized scene-graph coordinates and z-order.
- Add native editable text boxes for fill slots. `ordinary-text` needs exact approved `content` in the deck spec, except an action-title slot may inherit the slide title; deliberately blank ordinary text needs `user_fill_required: true`. `ordinary-data` stays value-free and visibly framed. Never put a fake number or sample series into a chart/table shell.
- Keep source aspect ratio unless the scene graph explicitly records a crop.
- Update the scene graph when any placement is changed during assembly.
- Render the assembled deck for QA; do not judge only from object metadata.
- Describe editability honestly: PNG components are movable, scalable, crop-able, replaceable, and layerable, but their internal paths and colors are not native PowerPoint shapes.
- When notes are in scope, follow `narrative-and-speaker-notes.md`: the canonical string is `deck-spec.json.slides[].speaker_notes`. Assembly embeds it in the native notes body by slide ID, including pilots/previews, and records its normalized UTF-8 hash. Validation reopens the PPTX and checks notes as well as visible objects; a standalone talk-track file is not embedded-note evidence.

## Object-level assembly contract

For production, first select a representative busy content slide in `pilot-plan.json`, complete only its assets, and run `python scripts/assemble_editable_pptx.py <project-dir> --version <pilot-version> --pilot-slide <slide-id>`. This creates a separate one-slide PPTX and immutable pilot assembly map; it does not write the final `assembly-map.json`. Render with the verified PowerPoint backend (no `--no-render`), then run `python scripts/render_pilot_review.py <project-dir> --version <pilot-version>`. The packet remains pending until the human explicitly approves it. `python scripts/validate_project.py <project-dir> --stage pilot` must pass before making the other slides' assets. Any changed pilot page, selected asset, actual PPTX, render, or review evidence invalidates the trial decision.

Run `python scripts/assemble_editable_pptx.py <project-dir> --version <new-version>` only after `--stage assets` passes. It refuses overwriting a prior version. Each approved scene instance becomes one named PPTX picture (`APW:visual:<instance-id>:<component-id>`), including repeated placements and opaque ordinary photo rectangles; each fill slot becomes one named native text box (`APW:slot:<slot-id>`). The script rejects near-full-slide raster placement, unsupported opacity, and photo aspect distortion. Concept images and textless masters are never embedded.

After the canonical assets pass, separate page workers may run `--preview-slide <slide-id>` concurrently with **different** `--version` values such as `<batch>-S07`. Each command writes one editable slide and one local assembly map under its own `previews/` version directory; with rendering enabled it also writes one actual page render under `reviews/previews/<version>/`. It does not write the final `assembly-map.json`. Keep deck, scene, manifest, style, and assets frozen during these commands. The current preview command still performs its own preflight and the PowerPoint backend may limit safe render concurrency; use a bounded worker count and measure wall time rather than starting one process per component. If concurrent PowerPoint rendering is unsafe, use `--no-render` for parallel structural page drafts and reserve visual QA for the final PPTX render. Once all pages have been structurally checked, the main agent runs the full assembler above **once** from those same canonical inputs. This rebuild is the final merge, not a ZIP-level splice of single-page PPTX files. Validate the final PPTX and inspect its own renders; preview renders are not final-deck evidence.

The script records the current deck/scene/manifest/style hashes, every object and slot, PPTX hash, and 1920×1080 PowerPoint renders in `assembly-map.json` with `status: structure-assembled-visual-review-pending`. `--no-render` is diagnostic only and cannot pass assembly validation. The public validator reopens the PPTX and compares each picture's bytes, identity, geometry, rotation, and z-order and each text box's content/size to the approved inputs; it rejects direct PPTX-only edits or a flattened replacement. A render plus structural PASS still requires full-size human concept comparison at the next QA gate.

Run `python scripts/prepare_deck_qa.py <project-dir> --version <new-qa-version>` once after the whole-deck assembly passes. It writes one full-size concept/render pair, side-by-side image, overlay, and review packet per page under `reviews/qa/<version>/`, plus a contact sheet computed from the actual slide renders and pending exception/deliverable indexes. No page is automatically approved. For formal QA, humans inspect every page at presentation size and use 100% pairs to investigate suspected P0/P1 defects; they mark all nine `qa-report.json.slides[].checks` true only when warranted, set `status: passed`, reviewer and timezone-aware `reviewed_at`, and record any issues. A human reviewer also marks the five whole-deck checks and sets `final_reviewer` after inspecting the contact sheet. Then run `python scripts/finalize_deck_qa.py <project-dir>` and `python scripts/validate_project.py <project-dir> --stage qa`. The finalizer only promotes current passing human evidence to formal visual QA; it does not grant G5 release. For a user-authorized local draft, use separate hash-bound agent QA, possibly in parallel page shards, and leave the formal QA report pending. If a page fails, retain the draft and issue record, repair only its owning artifact, assemble a new version, and prepare a new QA version. The prepare command archives the previous pending/rejected report as `reviews/qa/<old-version>/qa-report.snapshot.json` before switching the current report; it refuses to overwrite a passed/released QA report. Never reuse a stale QA packet or silently flatten a difficult page.
