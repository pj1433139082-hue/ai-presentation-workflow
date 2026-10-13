# AI Presentation Workflow

This glossary separates shared production facts from route-specific approval language. `showcase-v1` is a local design route; G1–G5, decomposition approvals, and formal release terms belong to the strict production/component-first contracts unless a project explicitly invokes them.

## Terms shared across routes

**Local showcase delivery mode**:
The selected endpoint for a local showcase: `concept` (default; concepts only), `assets` (concepts plus requested transparent assets), or `assembly` (concepts, assets, and automatic PPTX assembly). The verified CLI stores this choice in `delivery-mode.json`; `status`, `check`, `build`, and `export` follow the selected endpoint. A showcase missing `delivery-mode.json` remains on legacy assembly compatibility. See the [three-mode examples](examples/showcase/modes/index.html). The mode limits production work in scope; it does not change truth, source, or review-authority requirements.
_Avoid_: every showcase must assemble, transparent assets by default, inferred permission

**Presentation route**:
The project-scoped workflow contract used for a deck. `contract_version: showcase-v1` with `purpose: showcase` selects the local showcase procedure. This metadata identifies the procedure; it does not grant external-release authority or prove user approval.
_Avoid_: automatic permission, human approval

**Contentful concept**:
A versioned design for a slide with its current copy, factual/example status, source lineage, and visual composition. It is a complete deliverable in `concept` mode and can guide assembly when assembly is selected. It is not the final editable slide or proof that the user has reviewed it.
_Avoid_: final render used as prior concept, flattened slide background

**Object/editability map**:
A per-slide record of meaningful content and visual objects, their sources, intended PPTX object types, and the edit operations promised for each. It connects concept regions to the assembled objects and review evidence.
_Avoid_: “editable” without an operation, picture equals native editing

**Actual PPTX render**:
A rendered page produced from the current assembled PPTX, identified with the PPTX and render versions/hashes. Concept previews and external builder screenshots do not substitute for it.
_Avoid_: concept-only QA, stale render

**Agent chosen**:
A design direction selected by an agent within explicit project authorization. Record the choosing actor, reason, and reference/concept versions. It is not a user decision or approval.
_Avoid_: human-approved direction, inferred permission

**Agent QA**:
An actual inspection by a named agent of identified current PPTX renders and deck scope, with recorded evidence and findings. It does not represent human review or aesthetic acceptance.
_Avoid_: human approval, formal QA approval

**Style preference feedback**:
The user's preference about visual directions or concept images they have seen. It may guide later exploration, but it does not accept an assembled PPTX, unseen pages, or a changed version. Record the exact concepts and response scope.
_Avoid_: deck acceptance, blanket approval

**User visual feedback**:
The user's actual response to a specific version and scope they have seen. Feedback, acceptance, and rejection are distinct; a response about a pilot does not cover unshown pages or later versions.
_Avoid_: blanket approval, inherited approval

**Formal release**:
The final package authorized by the independent G5 release decision after the strict production evidence passes. A local showcase or draft export does not grant this authority.
_Avoid_: export success, draft delivery

## Strict production terms

**Current review packet**:
A concrete set of current review artifacts and decisions presented to a user and bound to their versions and contents. An affirmative applies only to the stated packet and scope.
_Avoid_: blanket approval, inherited approval

**Local production authorization**:
The user's explicit preference to continue reversible local production with fewer procedural confirmations under a named project scope. It does not prove an artifact was seen, authorize an agent to make unrelated brand/factual decisions, or grant formal release authority.
_Avoid_: automatic approval, release authorization

## Component-first terms

The following terms describe the existing component-first route. They do not make every hybrid/showcase deck use transparent PNGs or a decomposition gate.

**Page shard**:
A slide-owned draft of component-first production records prepared against that slide's current approved inputs. It remains a draft until the main owner reconciles it with the whole deck.
_Avoid_: canonical inventory, approved component library

**Canonical inventory**:
For component-first work, the reconciled whole-deck account of textless masters, transparent components, and scene placements. Its coverage follows the applicable decomposition contract.
_Avoid_: page shard, generic hybrid object map

**Contentful review concept**:
A component-first review image with the approved title, concise copy, truth/status labels, and representative imagery. It is a visual contract for later decomposition, not a final flattened slide.
_Avoid_: final slide, whole-page PPTX background

**Textless component master**:
A post-concept component-first intermediate with ordinary copy and data removed while the composition and fill-slot geometry remain. It is not an independent visual component.
_Avoid_: transparent component, final background

**Independent visual component**:
A visual object extracted or generated as a separately movable/recombinable image under the component-first contract. Its internal pixels are not native PowerPoint shapes or text.
_Avoid_: native editable object, textless page image

**Decomposition list**:
The component-first review record mapping visible objects to independent image components and fill slots.
_Avoid_: filename-only asset list

**Recomposed page**:
A component-first page rebuilt from approved image components and editable content for comparison with its concept.
_Avoid_: concept image, textless master

**Visual fidelity**:
For component-first reconstruction, the rebuilt page preserves the approved concept's composition, hierarchy, colors, content, and main relationships. Small texture variance alone is not missing content or a usability defect.
_Avoid_: pixel identity, aesthetic approval
