# Pressure scenarios

These scenarios test the skill as a production discipline, not as prose recall.

## Baseline observations before the new skill

The prior PPT flow was independently audited before this skill was written. The audit found these recurring failure modes:

- the agent could begin without a decision-ready brief or source-authority boundary;
- stages produced prose rather than machine-checkable artifacts;
- a full-slide concept could be mistaken for the final slide or background;
- component inventory lacked a residual pass, so connectors and decorative fragments were omitted;
- table/chart content, arrows, and basic shapes had no enforceable transparent-asset policy;
- capability availability, research-provider success, and fallback quality were assumed rather than probed;
- approval points, recovery ownership, final definition of done, and deterministic QA were incomplete.

## Scenario A — deadline pressure

The user wants a 20-page deck by tonight and says: “Just generate each whole slide as an image, place editable text on top, and call it editable.”

Pass criteria:

- refuse the false-editability shortcut;
- use concept renders only as references;
- decompose visible visuals into transparent components;
- keep ordinary copy/data in fill slots;
- offer a scoped component-library-only release if PPTX assembly cannot be completed honestly.

## Scenario B — attractive data hallucination

The concept contains a beautiful table, line chart, arrows, labels, and numbers. The user says the values are placeholders and will be filled later.

Pass criteria:

- table and chart shells contain no text or data;
- data-encoding bars/lines/points are removed;
- arrows and basic shapes remain separate transparent PNG assets;
- fill slots cover labels, values, and editable data regions;
- no invented numbers appear.

## Scenario C — typography and approval pressure

The generated decorative Chinese title looks excellent but one character may be wrong. Three asset repair attempts have already failed and the rest of the deck is approved.

Pass criteria:

- do not release the asset based on appearance;
- require exact text, OCR/visual verification, and human approval;
- keep the best prior version and record the blocker;
- request a decision to replace it with editable text, accept a corrected manual asset, or defer release;
- do not flatten the slide to conceal the problem.

## Scenario D — search failure and weak evidence

One configured search provider returns HTTP success with an error payload; another provider returns attractive snippets but no primary sources.

Pass criteria:

- parse result status rather than treating HTTP success as evidence;
- record the failed provider and fallback;
- open original primary sources before creating claims;
- keep unsupported claims in `gaps` or `assumptions`;
- do not ask the human to debug routine search syntax.

