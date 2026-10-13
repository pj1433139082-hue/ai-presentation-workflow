# Visual provider registry and PPT adapters

The presentation workflow owns story, style coherence, scene graph, assets, approvals, assembly, and release. A visual skill is a bounded provider, never the full-deck renderer.

Before any production provider generates a concept, complete `reference-study.json` and use the selected project-local images plus analyzed transferable rules. Provider examples may enter that study, but provider selection does not itself count as reference analysis.

## Registry contract

`visual-provider-registry.json` records, for every provider:

- supported page roles;
- supported component roles;
- required source material;
- truth-sensitive policy;
- ordinary-text and data policy;
- aspect-ratio behavior;
- real-alpha transparency behavior;
- human approval requirements;
- output class and PPT adapter;
- whether automatic routing is allowed.

The registry is schema `1.0` and contains the canonical seven-provider safety contract. Changing a tier, truth policy, source or approval requirement, source route, page/component role, output class, transparency behavior, aspect behavior, or adapter requires a coordinated code/test version change; runtime edits that relax those combinations are rejected.

Reject a provider when any requested page role, truth policy, text policy, transparency promise, or output class is incompatible. Do not silently accept its native full-page output.

## Routing policy

`style-contract.json` names exactly one `primary_visual_family`. Every other slide-level provider must be listed in `secondary_provider_roles` with a narrow set of page roles. A provider can be selected only when its registered page role and the style contract both allow it.

The seven registered providers have these boundaries:

| Provider | Tier | Allowed use |
|---|---|---|
| `guizang-material-illustration` | core auto | conceptual components, structures, processes, mechanisms |
| `photo-postprocess-coach` | core auto | ordinary supplied photos, portraits, atmosphere photos; never product screenshots, data evidence, or reports |
| `scene-distillation-zine-v1-3` | core auto | opening, transition, closing, and abstract-metaphor anchors that are not truth-sensitive |
| `gc-minimal-zine-poster-v0-3` | explicit style | approved cover, section opener, or special poster only |
| `scenes-gathered-zine-v1-3` | explicit style | approved editorial montage, section opener, or narrative collage only |
| `surreal-pop-collage` | explicit style | approved campaign/creative opener or closing only |
| `guizang-social-card-skill` | post-release derivative | social card derived from a released deck; never a slide renderer |

Only the first three providers may be auto-routed. The three strong-style providers require both an explicit provider request and membership in `explicit_visual_opt_ins`. Scene Distillation and every strong-style provider reject truth-sensitive visuals. Social Card requires a released deck and the `post-release-derivative` deliverable role.

Route a request before invoking a provider:

```bash
python scripts/visual_adapters.py --mode route --registry <project>/visual-provider-registry.json --style-contract <project>/style-contract.json --project-root <project> --request <route-request.json> --output <selected-provider.json>
```

The route request contains `page_role`, `source_kind`, `truth_sensitive`, and `deliverable_role`. Add `provider_id` only for an explicit selection. Provider-specific evidence is mandatory:

- Photo Postprocess adds `source_rights_confirmation: {path, sha256}` and `source_photo: {path, sha256}`. The referenced JSON must contain `status: confirmed`, exact `approval_phrase: 确认素材使用权`, a non-empty `confirmed_by`, and the real source file path/hash. It must separately record `media_class: ordinary-photo`, `truth_sensitive: false`, exact `classification_phrase: 确认普通照片`, a non-empty `classified_by`, and true exclusions for `product_screenshot`, `data_figure`, and `report`. The router recomputes hashes, requires the request to name that same source, and requires the rights/classification record to be a current hash-locked G1 artifact. These are human classification claims, not image-content recognition; an ambiguous or disputed source must stop for review.
- Every explicit-style route adds `slide_id` and `special_page_approval: {path, sha256}`. The referenced JSON must match the provider, page role, and slide, use exact `approval_phrase: 确认特殊页面风格`, and itself be a hash-locked G4 `concept_contact_sheet` artifact.
- Social Card adds `released_deck: {path, sha256}` and `approved_derivative_brief: {path, sha256}`. `deck_released: true` is only an assertion: the router independently verifies approval identity/time, current decision values/hashes, full QA/slide evidence, real PPTX package structure, and exact `确认发布`; it then proves the requested deck is the exact `assembly-map.json` output and QA subject. The brief must bind that deck hash, while `run-state.json.post_release_derivatives.guizang-social-card-skill` must record approver/time, exact `确认社交卡衍生`, the same deck hash, and the approved brief hash.

A non-zero exit is a hard stop, not permission to fall back to a visually similar provider.

## Material Illustration adapter

`guizang-material-illustration` is a core automatic provider for conceptual illustrations, structural diagrams, processes, and mechanisms. It requires an approved concept render and style contract. It must not redraw screenshots, figures, equations, logos, plots, or other truth-sensitive evidence.

Its PPT adapter converts a provider-native idea into one record per visual object. Every arrow, basic shape, panel, node, illustration, table shell, and chart shell remains separate. Outputs are planned as real-alpha transparent PNG components generated with Codex `image_gen`.

Ordinary text and data are prohibited. Table/chart shells require fill slots and must remove labels, numbers, ticks, legends, bars, lines, points, and every other data-encoding mark. Decorative special typography is outside this adapter and follows the explicit OCR/human-approval exception.

Prepare a JSON request with `provider_id`, safe `slide_id`, `page_role`, `source_kind: approved-concept-render`, `truth_sensitive: false`, `deliverable_role: slide-asset`, the approved `style_contract_version`, and an `elements` array. Include `approved_style_contract` with the G3 version and SHA-256 plus `approved_references` with the G4 paths and SHA-256 values. Every element cites one or more paths from that approved set, provides a normalized `reference_bbox`, and uses safe component/fill-slot IDs. Do not supply a free-form component prompt: the adapter derives a fixed no-text/no-data prompt from the approved reference, crop, and component role. Before emitting any generator-ready prompt, the adapter also verifies the current explicitly human-approved post-G4 decomposition map, its review evidence and source hashes, and each requested component's role, treatment, and bbox. A stale or absent decomposition approval is a hard stop; caller-supplied approval claims are not sufficient. Then run:

```bash
python scripts/visual_adapters.py --registry <project>/visual-provider-registry.json --project-root <project> --request <request.json> --output <adapted-plan.json>
```

Treat a non-zero exit as a hard incompatibility. The adapted records may be merged into `asset-manifest.json` only after their page role and component IDs match the approved deck spec and scene graph.

New material plans default to `prompt_profile: v6`, which separates target, reference, preservation, role-specific content, canvas and exclusions. The profile is recorded on every emitted asset. Keep the emitted English prompt verbatim for generation and validation; use the user's language for surrounding explanation. A request may name an existing supported `prompt_profile` for reproducible replanning, but cannot supply custom component prose. Historical manifests with no profile mean `v1`; their prompt text is unchanged. Replanning or repairing an asset still requires its current source/decomposition evidence and the usual per-object output review. See [prompt patterns](prompt-patterns.md) for the selected gallery patterns and concept examples.

Every provider-backed manifest record repeats the registered transparency and aspect behaviors. It repeats the registered `output_class` except for the photo provider, whose two concrete output classes are specified below. Project validation compares these against the canonical registry; a provider cannot relabel page art, transparent components, or post-release cards as another output class.

## Ordinary photo adapter

`photo-postprocess-coach` is only for a rights-confirmed ordinary photo, never a screenshot, report, data figure, or other fact-sensitive image. Its registry `output_class: photo-or-transparent-cutout` is a provider capability umbrella; each manifest asset must instead declare exactly one concrete class: `opaque-photo-rectangle` (`role: ordinary-photo`, `photo_output_mode: rectangle`) or `transparent-photo-cutout` (`role: photo-cutout`, `photo_output_mode: cutout`). Rectangles stay independently placeable image objects but need no alpha promise. Cutouts require a real-alpha PNG and per-object isolation review.

The adapter also rejects obvious flat raster graphics as a defensive tripwire. This heuristic can flag a low-texture real photo or miss a photorealistic screenshot; it never replaces the human source classification. If flagged or ambiguous, stop and inspect the source, then use the source-preservation/evidence route when factual fidelity matters. Do not bypass the stop by changing labels or recompressing the image.

After G4 and explicit decomposition approval, run `visual_adapters.py --mode adapt-photo` with a rights/classified `source_photo`, the approved style/reference records, `id`, `slide_id`, `reference_bbox`, and the approved `photo_output_mode`/`treatment`. `preserve-source` on a rectangle points to the original photo byte-for-byte. `photo-adjust` produces only a **plan** with `next_action: diagnose-photo-then-confirm-generation`; it does not call the image tool or invent an approval. Use `photo-postprocess-coach` to inspect the photo, record objective diagnosis evidence, show repair/style choices and the preservation recipe, and obtain a separate source-, diagnosis-, direction-, and recipe-bound `确认照片后期方案` before editing. Keep subject identity, architecture, perspective, and key scene content; the prompt or recipe must say so. Record every output attempt and render `render_photo_review.py` for a native-size source/output comparison. A human must pass all preservation checks, then also pass the standard concept/isolation review. The validator checks hashes and recorded decisions, not semantic identity by itself.
