# Technology showcase v3 — independent final acceptance review

- Actor: `agent`
- Reviewer: `/root/showcase_acceptance_plan`
- Reviewed at: `2026-10-12T20:05:40+08:00` (Asia/Shanghai)
- Frozen deck: `deck-草稿.pptx`
- Current PPTX SHA-256: `08efee414fd08d9c961c0830dc29f6cae0922b177a38b8a8dd1955f9913161ba`
- Frozen copy: `frozen\08efee414fd08d9c961c0830dc29f6cae0922b177a38b8a8dd1955f9913161ba\deck-草稿.pptx`
- Frozen copy SHA-256: `08efee414fd08d9c961c0830dc29f6cae0922b177a38b8a8dd1955f9913161ba` (matches current PPTX and machine QA)
- PowerPoint render: `Microsoft PowerPoint COM / PNG 1920x1080`; five 1920×1080 PNGs
- Machine QA: `issues=[]`; machine SHA-256 and all five render PNG hashes independently matched.

## Slide-by-slide visual review

| Page | Actual rendered image | Independent finding |
|---|---|---|
| 01 | `preview/slide-01.png` — SHA-256 `6bc052c38a6f075d3ef71a7946e3baefa0484765e358dcdcb27d553574b5ed5f` | P0: none. P1: none. P2: slide-number glyph is reported 3.56 pt wider than its text box; it remains legible and safely inside the canvas. Cover reads clearly; the generated connector illustration occupies the right third, not the slide background. Footer explicitly calls the product and capabilities a fictional concept. No unsupported capability or business-performance claim is presented as fact. |
| 02 | `preview/slide-02.png` — SHA-256 `8cc66b6d2a29814e35a09b7890cf00575bd1f4a466a81fcebdf8167ead1e7747` | P0: none. P1: none. P2: same minor slide-number text-box width report. The central context diagram has clear hierarchy and spacing. Sample questions are visibly framed as a fictional scenario; no survey or user-research evidence is implied. |
| 03 | `preview/slide-03.png` — SHA-256 `83896636e34058329a42a4a4d644cbd6feff6c26b2c5bb08b5edaf5836b96ff1` | P0: none. P1: none. P2: slide number as above; “相关线索 01” exceeds its text-box height by 0.46 pt in machine geometry, with no visible clipping. The editable concept UI and quote are readable; the footer and speaker note both identify project/date/quotation as fictitious. The small generated prism image is decorative and does not replace native text or the interface. |
| 04 | `preview/slide-04.png` — SHA-256 `b646cfc2357bbba47bd16c5d6e08475c8774995ee3222f599a36c8eb43ba1592` | P0: none. P1: none. P2: slide number as above; two small metadata labels exceed their boxes horizontally by about 4.1 pt, but remain fully visible on-canvas. Four-step process is easy to scan and leaves judgment with the team. Slide/footer and notes clearly state that access, versioning, and citation capabilities remain unvalidated. |
| 05 | `preview/slide-05.png` — SHA-256 `cebc8848a4275a9f111da73b9aa5b02b56fb09d6eddc9127011ed10639e9df77` | P0: none. P1: none. P2: slide number as above; two-line “建议验证项 / 非效果承诺” label exceeds its nominal text-box height by 2.98 pt, but is rendered clearly. Pilot scope, observations, and review steps read as a proposal; “非效果承诺” and fictional-scope footer prevent a performance claim. The illustration is a separate transparent PNG, not a flattened slide. |

## Object, source, and freeze checks

Five slides have editable native text and shapes on all pages (7/12, 12/19, 25/38, 18/26, 19/25 native-text/total-shape counts). Separate transparent image assets occur only on slides 1, 3, and 5; maximum picture bounding-box area is 22.1% of slide area. Speaker notes are present on every slide. No P0 or P1 issue found. The listed P2 items are small text-frame geometry discrepancies only; rendered content remains legible and within the slide canvas.

The two original visual assets in `assets/` are RGBA PNGs with alpha extrema `(0, 255)`. They are individual illustrations placed on a minority of slides; the slide backgrounds and all text/process diagrams are native PowerPoint content, not page-sized image fixtures. Speaker notes are present on all five slides.

Final result: **accepted with P2 notes; no P0/P1 finding.** The PPTX was not edited during this review. The current file, hash-addressed frozen copy, and `qa-machine.json` source hash match.
