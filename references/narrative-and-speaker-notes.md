# Narrative and presenter notes

Load during Story, when a slide is overcrowded, or when a talk track is part of delivery. Use the existing storyboard, brief, and deck spec; this guidance adds no approval gate.

## Plan the audience's reasoning

Start from the decision or understanding the audience needs. Assign each slide one job in that reasoning, then select its visual structure. Read the action titles consecutively: they should carry the argument without the body copy. Remove redundant pages and expose any unsupported jump before G2.

| Page job | Useful structure | What must remain clear |
|---|---|---|
| Establish the problem | Current condition → consequence → question | The actual scope and why this audience should care |
| Explain a mechanism | Inputs → transformation → outputs | Direction, dependencies, and exceptional paths |
| Compare options | Shared criteria across alternatives | Equivalent units and a visible reason for the recommendation |
| Present evidence | Large preserved figure plus a precise takeaway | What the figure supports and the limits of that inference |
| Teach a concept | Concrete example followed by the transferable rule | The learner's next task or check for understanding |
| Request a decision | Recommendation, tradeoff, and next action | Who decides what, and on which evidence |

These are starting points, not templates to rotate mechanically. The approved composition, readability, and semantic grammar contracts still apply.

Separate three channels: the slide's approved narrative message, the concise wording viewers see, and the explanation the presenter says. Keep essential conditions or uncertainty visible when omitting them would change the claim. Move elaboration, examples, and navigation into notes; do not move a decisive limitation there to make a stronger-looking slide.

If approved copy cannot fit, propose a shorter source-faithful realization or split the idea. Reconcile the changed story/copy with its owning gate. Do not silently reduce font sizes or change an approved slide count. Use any supplied speaking-time budget to allocate attention by page job; estimates require rehearsal and are not verified delivery times.

## Write the spoken explanation

Choose the voice from the audience and purpose: executives need the implication and decision; researchers need evidence and uncertainty; learners need definitions, examples, and checkpoints. Keep that voice consistent while giving difficult figures more explanation than a transition page.

Write a usable talk track in the deck's language. Start with the point, guide the audience through the actual visual in reading order, explain why it matters, and bridge to the next page when useful. Avoid reciting every visible bullet or adding generic filler. Notes may explain approved claims; they may not introduce unsupported metrics, quotations, outcomes, or stronger certainty. An empty data slot remains pending in the spoken explanation too.

Use stable slide IDs while editing. `deck-spec.json.slides[].speaker_notes` is the canonical plain-text source; an optional Markdown reading copy is derived from it. Do not maintain two independently editable versions or use numeric headings to bind notes after page reordering.

A reorder updates `storyboard.json` and `deck-spec.json` together and reconciles the affected existing story/concept review records. The validator compares their ordered slide IDs before assembly. Stable IDs keep a note with its page; they do not approve a new narrative sequence. When notes are part of the original brief, draft them with the deck spec and include their reading copy in the existing content-review packet before G4, reducing late changes to already approved hashes.

```json
{
  "id": "S07",
  "speaker_notes": "先看左侧的输入，再沿箭头看处理过程。这里要说明的是依赖关系，不能把这个示意图当作效果验证。\n\n下一页再讨论需要哪些证据来检验这条路径。"
}
```

When the user requests notes, record `delivery.speaker_notes: required` in `brief.json`; every planned slide then needs non-whitespace notes. Otherwise omit that delivery field or use `not-requested`, and do not invent notes merely to fill a template. A slide's optional `speaker_notes` must be a string; omission or an empty string means no notes. The assembler normalizes CRLF/CR to LF and rejects control characters unsupported by PPTX. Ordinary text, punctuation, paragraphs, and tabs remain text, never executable markup.

## Verify the delivered notes

`assemble_editable_pptx.py` writes notes into the corresponding native PowerPoint notes body for full decks, pilots, and page previews. Nonempty notes receive `speaker_notes_sha256` in that slide's assembly record. The object validator reopens the actual PPTX, compares each notes body with the current deck spec, and checks its recorded hash. It also rejects injected notes on a page that has none specified.

Notes are part of the hashed deck spec and PPTX. A later wording change requires a new assembly and the relevant existing approval/QA reconciliation; do not patch the final PPTX directly. During content review, check spoken claims alongside visible claims. Report embedded-note coverage when notes were requested; never count an external script alone as completion.

## Source of the selected idea

The separation of page composition and presenter speech was informed by [codex-ppt's production guide](https://github.com/ningzimu/codex-ppt-skill/blob/6d76c0eded7f8a8b0c4e304697e6f2bda7c408b2/skills/codex-ppt/docs/project-assembly-and-reporting.md). This workflow implements native notes against its own stable-ID and editable-component contracts; it does not use that repository's image-only assembler.
