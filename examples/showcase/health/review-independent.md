# Health-literacy showcase v3 — independent final acceptance review

- Actor: `agent`
- Reviewer: `/root/showcase_acceptance_plan`
- Reviewed at: `2026-10-12T20:05:40+08:00` (Asia/Shanghai)
- Frozen deck: `deck-草稿.pptx`
- Current PPTX SHA-256: `2d30119ed03c1e0e2da4d5e24b3e77b929bb49242d8d83aa86c031fa25154b2d`
- Frozen copy: `frozen\2d30119ed03c1e0e2da4d5e24b3e77b929bb49242d8d83aa86c031fa25154b2d\deck-草稿.pptx`
- Frozen copy SHA-256: `2d30119ed03c1e0e2da4d5e24b3e77b929bb49242d8d83aa86c031fa25154b2d` (matches current PPTX and machine QA)
- PowerPoint render: `Microsoft PowerPoint COM / PNG 1920x1080`; five 1920×1080 PNGs
- Machine QA: `issues=[]`; machine SHA-256 and all five render PNG hashes independently matched.

## Slide-by-slide visual review

| Page | Actual rendered image | Independent finding |
|---|---|---|
| 01 | `preview/slide-01.png` — SHA-256 `39fef056cb11f580cfd135930ee80c9cb3b4f6e2a6e5e3a7ebba35adfb58fa4d` | P0: none. P1: none. P2: slide-number glyph is reported 3.65 pt wider than its text box; it remains legible and within the canvas. Cover is calm and legible. The generated book illustration is a separate visual. Footer and notes state this is information-literacy education, not diagnosis or treatment advice. |
| 02 | `preview/slide-02.png` — SHA-256 `464ceef8c2169df8c1a55a9af9189500062e9274026e2c7bd2fd30c7fdca1291` | P0: none. P1: none. P2: same minor slide-number text-box width report. Four questions are distinct, ordered, and readable. Bottom MedlinePlus attribution is visible and not colliding with the page number. The prompts are consistent with the cited evaluation page. |
| 03 | `preview/slide-03.png` — SHA-256 `49eacb54865e2590cc6046cb8faf187fb9614ffea4d14dbfe2ef8161cd548451` | P0: none. P1: none. P2: central “结论 / 边界” text exceeds its nominal box by 9.59 pt vertically; four supporting captions exceed boxes by 0.52–1.24 pt. All are visibly legible, with no clipping or overlap. The diagram is balanced and presents evidence limits without ranking treatments or implying personal applicability. Source attribution is visible; the boundary reminder is explicit. |
| 04 | `preview/slide-04.png` — SHA-256 `aa5be0714dd73d85859493f07567114c5b544bdce592e7447a96e2a8807e5dff` | P0: none. P1: none. P2: quoted example headline extends 3.74 pt beyond its text-box height but remains fully legible. On-slide it is introduced as “你看到的” but is not explicitly stamped “虚构示例”; speaker notes and source file identify it as fictional. For any later outward-facing use, an on-slide fictional-example label would reduce ambiguity. The source-tracing line is understandable and readable. No treatment instruction or specific medical claim is given. Footer names MedlinePlus; notes clarify the quote is fictitious. |
| 05 | `preview/slide-05.png` — SHA-256 `04662e4e58155d68c2e3b9f34c471c019e2619be13de05615e7521117833bd38` | P0: none. P1: none. P2: slide-number glyph has the same minor text-box width report. Conversation prompts are readable and actionable as questions. The closing sentence explicitly directs important personal health decisions to a medical professional; the footer repeats that this is not individualized medical advice. |

## Object, source, and freeze checks

Five slides have native editable text and shapes throughout (6/11, 19/24, 15/22, 14/21, 15/25 native-text/total-shape counts). Separate transparent illustrations occur only on slides 1 and 5; maximum picture bounding-box area is 21.6% of slide area. Every slide has speaker notes. The source map cites MedlinePlus “Evaluating Health Information”; the official page advises asking questions about site operator/purpose/funding/review/evidence/update dates and discussing information with a health-care provider before relying on it. These points match the deck’s scope. No diagnosis/treatment claims are presented. No P0 or P1 issue found; minor geometry flags and the optional visible fictional-example label are P2.

The two original visual assets in `assets/` are RGBA PNGs with alpha extrema `(0, 255)`. They are individual illustrations placed on a minority of slides; the slide backgrounds and all text/process diagrams are native PowerPoint content, not page-sized image fixtures. Speaker notes are present on all five slides.

Final result: **accepted with P2 notes; no P0/P1 finding.** The PPTX was not edited during this review. The current file, hash-addressed frozen copy, and `qa-machine.json` source hash match.

Source spot-check: [MedlinePlus, Evaluating Health Information](https://medlineplus.gov/evaluatinghealthinformation.html), accessed 2026-10-12. The official page asks readers to check who operates and funds a site, its purpose, editorial review, evidence sources, and update dates, and to discuss information with a provider before relying on it. The deck presents these as a simplified literacy checklist, not as medical advice.
