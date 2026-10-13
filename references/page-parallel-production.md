# Page-parallel production

> Scope: This worker/shard sequence is the legacy component-first production method; local showcases may delegate design work under the current project scope but must reconcile references, concepts, objects, versions, and whole-deck review through the showcase contract.

The unit of parallel work is one slide, not one shared project JSON file. This route shortens the time between approved concepts and a checked deck without adding a user decision per page. Use bounded child-agent tasks in the current conversation; each worker owns disjoint slide IDs and paths. The main agent owns every canonical merge and the final PPTX.

## Self-contained page handoff

Give a worker a saved page brief, for example `page-shards/<batch>/<slide-id>/job.md`, so it does not depend on the parent's chat history. Include:

- its slide ID, active stage, permitted writes, frozen artifact versions/hashes, and absolute input/output paths;
- the approved page job, copy/fill-slot bindings, reference rules, and current calibrated exemplar;
- a role for each input image: style only, approved geometry, preserved factual evidence, or target component; style references must not contribute factual content, while evidence keeps its source pixels;
- the actual visual provider/tool used for this stage, its supported reference-input preparation, and the applicable generation/extraction adapter; do not infer availability from a backend name;
- the required fragment, isolation/preview evidence, retry budget, and a concise return record: slide/stage, ready or blocked, files/hashes, actual tool, attempts, and P0/P1 findings.

The existing fragment schemas remain canonical; the brief is a handoff aid, not another state machine. A returned path is a candidate until the main owner verifies the real file and its bindings. A blocker reports the failing dependency and exact slide/stage evidence. Keep independent pages moving where possible, without changing the visual route or fabricating completion. Speaker notes are supplied from the canonical deck spec, never rewritten by a page assembler.

This handoff pattern is informed by [codex-ppt's slide-worker contract](https://github.com/ningzimu/codex-ppt-skill/blob/6d76c0eded7f8a8b0c4e304697e6f2bda7c408b2/skills/codex-ppt/prompts/slide-worker.md); ownership and merge barriers below remain this workflow's own contracts.

## 1. Frozen concept, parallel decomposition

Once a contentful concept candidate exists, workers may draft a component list and identify fill slots for their assigned slides in `page-shards/<batch>/<slide-id>/`. These are speculative notes only: no approved master, asset, or global inventory is created before G4. If a candidate changes, discard or revise only that page's draft.

After the **current full-deck G4 approval**, give each page worker the approved concept path/hash, deck-slide hash, style version, fill-slot map, and unique `slide-id`. In parallel, each worker follows the local order `textless master → 100%-scale geometry evidence → semantic and residual inventory → numbered decomposition draft → scene instances`. A worker writes only its page-shard files and slide-owned image paths; it never edits `component-master-manifest.json`, `decomposition-map.json`, `scene-graph.json`, `run-state.json`, or another page's files. After the main merge, the canonical numbered image/list renderer runs once per page under the main owner because it writes the shared map. A page cannot start asset generation merely because its draft is ready.

The main agent checks that every deck slide has exactly one current shard; concept and deck-slide hashes match; component, instance, and fill-slot IDs are unique or explicitly approved reuse; and all visible items and truth-sensitive sources are accounted for. Merge the accepted page records in deck order into the canonical master/decomposition/scene files, then run the existing inventory validator. Present **one full-deck numbered decomposition packet and one scoped decision**. This is a merge barrier, not 18 new user gates.

Use `scripts/merge_page_inventory.py <project-dir> --batch <batch> --version <version>` for this merge. Each `page-shards/<batch>/<slide-id>/inventory.fragment.json` is an object with exactly `schema_version: 1`, `slide_id`, `bindings`, `master`, `decomposition`, and `scene`. The last three fields are that page's records from the corresponding canonical documents. `bindings` is the result of `merge_page_inventory.shard_bindings(root, deck_slide, style_contract, run_state)`: concept path/hash, deck-slide and fill-slot hashes, style version/hash, G4 artifact version, and canonical asset-manifest hash. Freeze those inputs while workers run. Workers omit `review_image`, `review_packet`, and `coverage_review`; the main owner prepares and presents canonical review evidence.

The command checks current G4 and the complete candidate's structural/master/scene/asset contracts in memory before writing. Instance IDs are globally unique; item and fill-slot IDs remain slide-local. Reused component IDs use the unique canonical asset-manifest record and its complete page ownership. Missing, duplicate, stale, conflicting, or worker-approved shards fail without changing canonical files. The existing asset manifest is not modified by this merge.

The merge publishes canonical **drafts**, leaving human coverage and decomposition approval pending. The main owner renders every numbered page serially, presents the full packet, records the actual coverage review and one current scoped decision, then requires the ordinary inventory validator to pass before assets. The public validator remains strict; it cannot infer visual coverage from records alone.

A three-file transaction guard blocks project validation during publication. In-process failure restores prior bytes; a stopped writer can be recovered with `python scripts/merge_page_inventory.py <project-dir> --recover`, then the same batch retried. Verify that the writer has stopped before recovery. Recovery refuses altered backups or unrelated canonical changes. Successful transactions retain previous drafts in `reviews/inventory-merges/<version>/`; do not reuse a committed version after review data changes. A crash before guard publication leaves only unused preparing files and makes no canonical change.

## 2. Parallel components after the pilot

The representative busy-page pilot remains a single prerequisite. Once its trial is approved or agent-verified under the authorized local policy, assign the remaining slides to page workers. Each worker writes components only to its slide-owned asset paths (for example `assets/S07/`) and a page-local asset-record fragment under `page-shards/<batch>/S07/`; it keeps every attempt, source hash, alpha evidence, and reuse link. No worker writes the canonical `asset-manifest.json`. If a component is reused across pages, assign one owner for its bytes and have other pages refer to that component ID; do not regenerate it in parallel.

Each worker can prepare its isolation sheets without touching the global manifest by passing its fragment to the renderer:

```bash
python scripts/render_asset_isolation_review.py <project-dir> --asset C-S07-D001 --manifest-fragment page-shards/<batch>/S07/asset-manifest.fragment.json
```

The fragment must be JSON with `slide_id` and an `assets` array. Distinct workers use distinct fragment files and asset IDs; the renderer writes its pending isolation record back into only that fragment. Reviewers record actual P0/P1/P2 decisions there under the existing low-friction or strict rules. The main agent then runs the single-owner merge and validation:

```bash
python scripts/merge_page_assets.py <project-dir> --batch <batch>
python scripts/validate_project.py <project-dir> --stage assets
```

The merge preserves existing pilot assets, rejects missing pages, duplicate/conflicting IDs, stale output hashes, and assets without a passed isolation review. Do not call the renderer without `--manifest-fragment` concurrently, because its default mode rewrites the canonical manifest. A material defect returns only its owning page/asset to repair; P2 cosmetic variance passes.

## 3. Parallel single-page PPTX assembly

After the canonical scene and asset manifest are frozen and `--stage assets` passes, assemble independent one-page PPTX previews in parallel. Give each worker a unique version containing its slide ID; the existing `--preview-slide` mode writes to disjoint `previews/<version>/` and `reviews/previews/<version>/` paths:

```bash
python scripts/assemble_editable_pptx.py <project-dir> --version <batch>-S07 --preview-slide S07
```

Each worker checks its actual one-page render against the approved concept at presentation size and reports P0/P1 issues, hashes, and reviewer. A preview is page-level assembly evidence; it does not write `assembly-map.json` or count as the final deck. Freeze shared inputs while these commands run. Do not reuse a version string between workers. If the PowerPoint backend cannot isolate concurrent renderer instances, build page previews with `--no-render` in parallel as structural drafts and render/check the final deck once; do not call an unrendered preview visually approved.

The main agent then runs the existing full-deck assembler **once** from the same approved scene and assets, in deck order. This rebuild is the final merge; do not splice single-page PPTX ZIP parts together, because their slide/media relationship IDs and layouts are not interchangeable. Validate the final PPTX and render every final page. Compare each final page's object/slot records and render with the accepted one-page preview; inspect any changed render for P0/P1 at presentation size rather than demanding pixel identity. Review the final contact sheet once for cross-page rhythm, semantics, and truth status. Only the final PPTX and its own renders can pass whole-deck QA or enter the three-folder handoff.

## Ownership and invalidation

- Worker: only its page shard, slide-owned components, page preview, and read-only findings.
- Main agent: unique-ID and current-hash checks, canonical JSON merge, pilot decision recording, final PPTX/`assembly-map.json`, whole-deck QA reconciliation, and handoff.
- Changed concept invalidates that page's shard and its later artifacts. Changed style or a reused asset may invalidate several pages. Changed global scene/manifest after page previews requires new previews for affected pages; the final assembler and validator always use the current canonical files.
- Formal G4, decomposition, strict-mode human checks, and G5 retain their existing authority. Parallel work changes scheduling, not who may approve them.
