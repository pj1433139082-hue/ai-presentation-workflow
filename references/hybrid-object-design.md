# Hybrid PPTX object design

Use this guide only when the selected deliverable includes automatic PPTX assembly and mixes native PowerPoint content with illustrations, photos, or preserved evidence. It does not require every visual to become a PNG. The object model described here is a target contract: a type is supported for a project only after the current backend can create, save, reopen, edit, and render it correctly. See the [three-mode examples](../examples/showcase/modes/index.html) for the distinct concept, asset, and assembly handoffs.

The local showcase modes stop at different points: `concept` (default) delivers concepts without object mapping or forced asset splitting; `assets` adds only the requested transparent visual components and stops without PPTX assembly; `assembly` continues into the object choices below. Do not apply assembly constraints to concept exploration.

Apply [stage-feedback.md](stage-feedback.md): confirm the complete concept batch before asset production, confirm the asset batch before PPTX assembly, then show the current actual PPTX renders and wait for feedback before the final handoff. Object-level verification remains internal to each consolidated stage review.

## Select an object from the user's editing need

Before assembly, map each meaningful concept region to its content, source, PPTX object type, and promised edit operation. Prefer the simplest object that preserves both the visual relationship and the requested editing behavior.

| Content or visual | Candidate object | State the real editability |
|---|---|---|
| Titles, body copy, labels, footnotes, values | Native text | Text and formatting can be edited in PowerPoint; text matches the current copy/source map. |
| Panels, simple geometry, dividers, ordinary arrows/connectors | Native shape or connector | Geometry, style, and text can be edited or selected/grouped as tested. Do not require raster components for basic geometry. |
| Structured rows/columns | Native table | Cell text/values and intended formatting can be edited; preserve units, labels, and source/example state. |
| Quantitative relationship | Native chart, when the selected chart type and data-edit path are supported | Verify series, labels, units, values, and the real PowerPoint data-edit operation. A chart-shaped picture is not an editable chart. |
| Complex illustration, texture, photograph, or collage | Independent picture object | It can be selected, moved, scaled, cropped/replaced as tested. Pixels, paths, and text inside the picture are not native editable objects. Transparency is needed only for a cutout/layering requirement. |
| Source screenshot, published figure, or factual image | Preserved evidence picture with source binding | The source image remains identifiable and its factual content is not silently redrawn or altered. Use native overlays separately if needed. |

If the selected backend cannot support the promised operation, report the gap and change the design, choose a verified backend, or narrow the promise with the user. Do not make a shape look editable by rasterizing it, or make a picture look fact-editable by putting an unrelated data table elsewhere.

## Map and verify the assembled objects

The object/editability map should link each concept region to its source and assembled object ID. For data, bind the values, units, labels, and calculation/source record. For pictures, bind the source or generation record and say whether the image is illustrative, photographic, or preserved evidence. Mark example values visibly in the slide and its source record.

After assembly, inspect the actual PPTX rather than trusting the map alone:

- Reopen the saved PPTX and confirm that text, shapes/connectors, tables, charts, and picture objects are the declared types and contain the expected copy/data.
- Exercise the promised edits on representative objects: change text, geometry/style, table cells, chart data/labels, or replace/move the image as applicable. Do not claim an edit operation that was not attempted or cannot be reproduced.
- Render the reopened PPTX and compare every page with its pre-assembly contentful concept. Check hierarchy, relationships, reading order, clipping, and whether the object choice obscures the intended message.
- Bind checks and review findings to the current source, concept, assembly, PPTX, and render versions/hashes. If one changes, recheck dependent evidence.

Technical success establishes that the PPTX contains functioning object types and accurate content. Agent visual QA records what an agent actually inspected. Neither result means the user accepted the design.

## Preserve the component-first option

When the user requests selected standalone transparent images in `assets` mode, deliver those images with their source/generation lineage; this does not by itself invoke the full legacy decomposition sequence or require a PPTX. Select the existing component-first route when the user explicitly wants the entire artwork delivered as an independently movable/recombinable layer library under that route's contract. Keep its textless masters, transparent components, inventory, decomposition, isolation, and strict/authorized-local review rules. Do not silently replace that promised library with native shapes just because a mixed-object deck is simpler.

A hybrid deck may still use separate picture components where their internal pixels do not need editing. The two strategies can coexist only when the project contract describes the resulting object types; one deck should use one verified PPTX assembly backend, not mix incompatible backend internals.

## Capability and implementation boundary

The current three-page hybrid sampler has empirically exercised native title text, connectors, a native table, a native line chart, and a separate picture object through PowerPoint save, reopen, render, and edit checks. This evidence applies only to those tested object types and operations in that sampler; it does not establish support for every shape, chart type, or layout. The sampler's technical checks and agent QA passed, but the user rejected its assembled visual result (“概念图不错，到你拼接就开始丑”). It is not a user-accepted deck. Consult current APW check output and test the saved PPTX before promising other support. Unsupported custom paths, SmartArt, animation, or chart variants stay out of scope until verified; do not silently flatten them into an image while retaining an editability claim.

Never place a full-slide concept image as the final slide background. A picture object may be a single intentional illustration or photograph, but it must not conceal copy, values, data, or slide structure that the user expects to edit.
