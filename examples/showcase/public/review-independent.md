# Independent production QA｜公共服务说明（public-v3）

- Reviewer / actor: agent `/root/showcase_production_plan` (Codex independent production reviewer)
- Reviewed at: 2026-10-12 20:05:39 Asia/Shanghai
- Scope: read-only independent visual review of all five full-size PowerPoint renders; inspect current deck identity, frozen copy, machine QA, page-level source notes, object editability, and rendered images. This review is agent-authored and is not human G5 approval or a claim that the formal workflow gates passed.

## Artifact identity and render binding

- Current `deck-草稿.pptx` SHA-256: `346ee1a784c207084f6ed5b11db6f38e9061fa76b0111bbae46ffb40fdcc521f`
- `qa-machine.json` deck SHA-256: `346ee1a784c207084f6ed5b11db6f38e9061fa76b0111bbae46ffb40fdcc521f` (matches current deck)
- Frozen copy SHA-256: `346ee1a784c207084f6ed5b11db6f38e9061fa76b0111bbae46ffb40fdcc521f` (matches current deck)
- Machine QA records 5 slides, 16:9, PowerPoint COM rendering at 1920×1080, and zero static issues.
- All five PNGs in `preview` are 1920×1080; their SHA-256 values match the machine QA entries:

| Slide | PNG SHA-256 | Visual findings |
| --- | --- | --- |
| 01 | `708e914748455a87e308aa6d0dd3d2b5031af7be25bdaed7a32cfb05cb3cf766` | Cover hierarchy is clear. Library illustration is a single selectable component on a white circular medallion; no visible colored fringe against the pale background. Fictional-city disclaimer is readable. P0: none; P1: none; P2: none. |
| 02 | `ecf7e7f9ffad8fe4d917c3ba43af0b67471be14e190866e507a1dd717acd0ca4` | Three steps are evenly separated with captions beneath each; no crowding or orphan lines after the centering adjustment. The local-confirmation banner and proposed-flow footer remain readable. P0: none; P1: none; P2: none. |
| 03 | `1fe6427c353585fc307463a65ba0e8b134de25588687b9ac931ea5608280d919` | Concept plan and right-side wayfinding principles have distinct visual grouping. The entry marker, continuous route, and non-real-floor-plan caveat are legible. P0: none; P1: none; P2: none. |
| 04 | `18ac4e922fa997dff6c6c5b34ffd7dfbe73c0be36ab7281b10582be106792d37` | Announcement template and four-step reader path are balanced; all fields visibly remain pending local confirmation. No clipping or collisions observed. P0: none; P1: none; P2: none. |
| 05 | `6f4aa81f24b6cf29bd3fa016454b61b8647b19a1a3953711a181506c4ab8cb08` | Four locally verifiable items align with the pilot sequence; the closing note now fits as one line and does not collide with the footer. P0: none; P1: none; P2: none. |

## Editability and factual boundary

- The deck contains native PowerPoint text and shapes on all five slides, per-slide notes, and one independent illustration image on slide 1. It is not a set of full-slide images.
- The machine object inventory reports 90 text-bearing shapes. The illustration remains one image object; its internal building and people are not separately editable.
- `sources.md` correctly labels the city, library, service proposal, flows, floor plan, and pilot suggestions as fictional, proposed, or awaiting local confirmation. The slide content does not present an actual operating library or approved service plan.
- No visual P0/P1/P2 defect was found in the five rendered slides.

## P1 — stale artifact hashes in documentation

At review time, `sources.md` still lists deck SHA-256 `d1edb380073d7391aedf287314840fcfddd6cca3b8bf8ddb4031b00226142017`, and `qa.md` lists `b91c41052fa6e1a1c712dd3116285f18dc545eaaf18c0b1b28537d6c2719b209`; both differ from the current deck, machine QA record, and frozen copy. `qa.md` also says the current-hash render is pending and asks for the illustration-edge check, although preview now exists and has been inspected. Refresh these documentation values/status against the frozen current deck before treating the text records as current. This is a provenance/documentation issue; it does not invalidate the verified current deck-to-preview hash binding.

## P2 — small text-geometry measurements

`preview/actual-text-geometry.json` reports a 5.76 pt vertical text-bound overrun for the two-line cover title, 5.35 pt horizontal overrun for page-number text on each slide, and 4.26 pt horizontal overrun for the four “待属地确认” labels on slide 5. Each was fully visible in the corresponding PowerPoint render, with no observed glyph clipping, overlap, or collision with adjacent content. The independent visual check therefore found no user-visible layout defect; if strict shape-bound containment is required, widen or re-center those text boxes and rerender.

## Brand cross-check

The previously filed `brand/qa-independent-production-agent-final.md` still names current deck SHA `5f4d09bda2dcf8a834bd2ed38f778418d86ac0ac872c916604f417d694a3463a`; on this pass, `brand/deck-草稿.pptx`, its frozen copy, and `brand/qa-machine.json` all still carry that same SHA. Its preview binding remains consistent.
