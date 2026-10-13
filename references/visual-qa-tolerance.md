# Visual QA tolerance for PPTX reconstruction

Use this rubric for generated components, the representative trial, and the assembled deck. It changes **how visual differences are judged**, not the approved source, editability, decomposition, or delivery commitments. An approved concept is the reference for communication and style; pixel equality is required only for source-preserved factual material and explicitly selected preserve-pixels extraction.

## Severity, not pixel count

| Level | Examples | Decision |
|---|---|---|
| P0 — blocking | Wrong/missing approved copy, label, evidence status or source image; invented data; missing promised independently movable component; clipped/unreadable content; diagram relationship or direction changed | Repair before the slide passes. Verify against the original source or contract. |
| P1 — material visual defect | At normal presentation size, line weight or contrast changes the hierarchy, a connector becomes hard to follow, placement/crop conceals content, or a style mismatch dominates the slide | Repair the affected slide/asset once, re-render, and reassess at normal size. Escalate only if the remaining issue is still material. |
| P2 — acceptable variance | Small line-width, edge antialiasing, glow, shadow, texture, color or position differences visible mainly in a zoomed overlay; differences that do not alter meaning, legibility, brand, or independent movement | Accept. Do not regenerate, remask, ask for approval, or keep a repair loop for these differences. A short note is optional. |

Line width has **no universal pixel-perfect target**. For a 1920×1080 review, a roughly 1–3 px difference in a noncritical stroke is normally P2, but this is an illustration, not an automatic threshold. Even a smaller difference is material if it hides a direction/relationship; a larger decorative difference can pass if it remains unobtrusive at actual presentation size. Never turn a numeric line-width tolerance into a new mandatory measurement for every object.

## Review order and stopping rule

1. Check approved content, factual media, labels, readability, and editability structurally. These are exact where the source/brief requires exactness.
2. View the actual PowerPoint render at intended presentation size. Ask whether the page reads correctly, its main visual hierarchy is clear, and its meaning matches the approved concept.
3. Open the side-by-side or overlay only to diagnose an observed P0/P1 issue. Difference images and hashes prove which files were compared; they do not grade aesthetic quality. Zoomed inspection is reserved for factual pixel preservation, legibility, a suspect edge, or a material defect.
4. If only P2 differences remain, stop and pass. For P1, make the smallest repair and check the affected page. Do not exhaust a fixed number of attempts merely to match a line width. Reopen user review only if a material content, truth, brand, or editability decision changes.

Generate existing isolation and page packets where the current contract requires them, but their presence does not imply a pixel-match target. In an agent-authorized local draft, the agent records P0/P1/P2 and the actual reviewer; it does not relabel the result as human approval. All pages still receive one real-render visual pass. The whole-deck contact sheet checks rhythm and consistency, not microscopic alignment.

## Tool choice and evidence

Keep the existing python-pptx assembly plus PowerPoint rendering for this change. No new reconstruction model, PPTX library, SSIM/LPIPS dependency, or additional gate is needed to lower the visual threshold. Overlays remain a diagnostic tool; the reviewer makes the severity decision in the context of the slide.

The original SSIM paper explains why simple pixel error does not reliably track perceived quality: https://www.cns.nyu.edu/pub/lcv/wang03-preprint.pdf . Microsoft's PowerPoint accessibility guidance calls for checking actual readability and warns that its checker misses some contrast arrangements: https://support.microsoft.com/en-us/accessibility/powerpoint/make-your-powerpoint-presentations-accessible-to-people-with-disabilities . These sources support a perceptual/use-based review, but the P0/P1/P2 thresholds above are this workflow's project judgment, not a published standard.
