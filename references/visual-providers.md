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

- Photo Postprocess adds `source_rights_confirmation: {path, sha256}`. The referenced JSON must contain `status: confirmed`, exact `approval_phrase: 确认素材使用权`, a non-empty `confirmed_by`, and the real source file path/hash. The router recomputes both hashes and requires the rights record to be a current hash-locked G1 artifact.
- Every explicit-style route adds `slide_id` and `special_page_approval: {path, sha256}`. The referenced JSON must match the provider, page role, and slide, use exact `approval_phrase: 确认特殊页面风格`, and itself be a hash-locked G4 `concept_contact_sheet` artifact.
- Social Card adds `released_deck: {path, sha256}` and `approved_derivative_brief: {path, sha256}`. `deck_released: true` is only an assertion: the router independently verifies approval identity/time, current decision values/hashes, full QA/slide evidence, real PPTX package structure, and exact `确认发布`; it then proves the requested deck is the exact `assembly-map.json` output and QA subject. The brief must bind that deck hash, while `run-state.json.post_release_derivatives.guizang-social-card-skill` must record approver/time, exact `确认社交卡衍生`, the same deck hash, and the approved brief hash.

A non-zero exit is a hard stop, not permission to fall back to a visually similar provider.

## Material Illustration adapter

`guizang-material-illustration` is a core automatic provider for conceptual illustrations, structural diagrams, processes, and mechanisms. It requires an approved concept render and style contract. It must not redraw screenshots, figures, equations, logos, plots, or other truth-sensitive evidence.

Its PPT adapter converts a provider-native idea into one record per visual object. Every arrow, basic shape, panel, node, illustration, table shell, and chart shell remains separate. Outputs are planned as real-alpha transparent PNG components generated with Codex `image_gen`.

Ordinary text and data are prohibited. Table/chart shells require fill slots and must remove labels, numbers, ticks, legends, bars, lines, points, and every other data-encoding mark. Decorative special typography is outside this adapter and follows the explicit OCR/human-approval exception.

Prepare a JSON request with `provider_id`, safe `slide_id`, `page_role`, `source_kind: approved-concept-render`, `truth_sensitive: false`, `deliverable_role: slide-asset`, the approved `style_contract_version`, and an `elements` array. Include `approved_style_contract` with the G3 version and SHA-256 plus `approved_references` with the G4 paths and SHA-256 values. Every element cites one or more paths from that approved set, provides a normalized `reference_bbox`, and uses safe component/fill-slot IDs. Do not supply a free-form component prompt: the adapter derives a fixed no-text/no-data prompt from the approved reference, crop, and component role. The adapter recomputes the files and compares them with `run-state.json`; caller-supplied approval claims are not sufficient. Then run:

```bash
python scripts/visual_adapters.py --registry <project>/visual-provider-registry.json --project-root <project> --request <request.json> --output <adapted-plan.json>
```

Treat a non-zero exit as a hard incompatibility. The adapted records may be merged into `asset-manifest.json` only after their page role and component IDs match the approved deck spec and scene graph.

Every provider-backed manifest record repeats the registered `output_class`, `provider_transparency_behavior`, and `provider_aspect_ratio_behavior`. Project validation compares all three with the canonical registry; a provider cannot relabel page art, transparent components, or post-release cards as another output class.
