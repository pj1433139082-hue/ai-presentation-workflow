# Local agent QA and draft delivery

> Scope: This record format is the authorized low-friction QA path within the legacy G1–G5 production pipeline. `showcase-v1` uses its own actual-render review record and does not populate this schema or claim formal QA/G5.

Use this only after actual inspection of every current assembled page and whole-deck contact sheet, under `run-state.json.local_review_policy: {"mode": "continuous-local", "authorized_by": "user"}`. Never fill records just to make export pass. `prepare_deck_qa.py` prepares verifiable evidence, not an inspection verdict. Preserve its pending-human `qa-report.json`; the agent record never finalizes formal QA or G5.

## Current scoped replies and review actors

A short user affirmation to the complete current packet uses `approval_mode: local-affirmative`, the actual `approval_phrase`, and the existing gate/version/decision/value/artifact bindings. Common replies include `同意`, `可以`, `好的`, `OK`, `确认`, `批准`, `是`, `yes`, and `通过`. This is not an echo phrase requirement. A compound correction, ambiguous answer, `继续`, or a previous approval cannot approve this packet. Reconcile corrections and present the affected current packet again. G1 cannot complete from a partial question frontier. State validation can verify scope and hashes, not prove what the user saw.

Master geometry and asset-isolation agent reviews retain their existing passed checks/evidence, and add `actor: agent`, `review_mode: agent-QA-user-authorized-continuous-local`, actual `reviewer`, and timezone-aware `reviewed_at`. Existing records declaring `review_mode: user-authorized-continuous-local` retain that historical local-authority meaning under the same user authorization/time/evidence checks; this alias never grants human authority. Human records may explicitly use `actor: human`, `review_mode: human`; historic human declarations without these fields remain compatible. Do not infer authority from a reviewer's name. Decomposition coverage, G1–G4/calibration decisions, photo preservation exceptions, formal deck QA, and G5 retain human authority. The pilot uses its existing `agent-verified-local` status under the canonical authorized review mode.

## Separate full-deck inspection record

Record `agent-qa-report.json` with:

- `schema_version: 1`, `review_mode: agent-QA-user-authorized-continuous-local`, `review_state: complete`.
- `qa_version`: the current prepared QA version; `pptx_sha256`: the current assembled PPTX hash.
- `contact_sheet: {path, sha256}`: the prepared whole-deck sheet made from the current renders.
- `slides`: exactly one record per deck slide, in deck order. Each has `slide_id`, actual `reviewer`, timezone-aware `reviewed_at`, `checks_performed`, current `bindings` and `evidence` from the prepared page packet, and `findings`.
- `whole_deck_review`: actual reconciler `reviewer`, timezone-aware `reviewed_at`, the five whole-deck `checks_performed`, current `contact_sheet_sha256`, `bindings` matching the prepared `deck_bindings`, and cross-slide `findings`.
- `outcome: issues` when any current P1 finding exists; otherwise `outcome: pass`. P2 cosmetic findings do not block. These are agent inspection outcomes, not formal QA statuses.

All nine page check IDs must appear exactly once: `independent_objects`, `geometry`, `hierarchy`, `color_and_z`, `content_truth`, `visual_relationships`, `readability_full_size`, `main_image_space`, `editability`. “Performed” means actually inspected, not automatically passed.

All five whole-deck check IDs must appear exactly once: `reference_transfer`, `composition_richness`, `readability_full_size`, `visual_coherence`, `truth_consistency`.

A finding has `slide_id`, `severity: P0|P1|P2`, a concrete `description`, `evidence: {path, sha256}` pointing to current reviewed page/contact evidence, `owner_stage: concept|inventory|assets|assembly|qa`, a concrete `repair_entry`, and integer `repair_attempts: 0..3`. Empty findings must be recorded as `[]`, not omitted. Repair history belongs in retained prior versions; current findings describe the inspected current artifacts.

The checker compares bindings with actual current files, reconstructs side-by-side/overlay and contact-sheet pixels, and requires independent current PowerPoint evidence for production. A changed concept, render, PPTX, scene, asset, style, story, reference study, or QA packet invalidates the affected record. The pending template is not evidence of a completed inspection.

## Delivery

Export and independent `--verify` share the same eligibility checks. Strict delivery requires current formal human QA. Authorized local draft delivery requires complete current agent QA. P0, missing inspection, or stale assembly/evidence blocks. A P1 permits a draft with `outcome: issues`; state explicitly that QA did not pass and link this project-side problem record alongside the package. Never label it agent-verified clean, human-approved, or released.

Keep exactly the existing three top-level delivery folders and a draft-labeled PPTX while G5 is pending. The problem record stays in the working project. A claimed release must pass the actual release validator, including current G5; an approved-looking status alone is insufficient. Freeze project inputs during export and its required independent `--verify`; do not run another project writer concurrently. The optimistic snapshot detects changes up to promotion and again during verification; it is not a lock on arbitrary external writers. Staged copying and verification publish only a complete new directory and never replace an existing delivery.
