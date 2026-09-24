# Research routing

## Preflight

1. Inspect the current workspace for an approved search policy or integration guide. If `20-规则层/29-搜索引擎API接入.md` is in scope, read it before invoking its script.
2. Probe available search tools at run time. Do not hardcode that a provider, engine, key, or quota is available.
3. Record the tool/engine actually used, date, query, filters, errors, and fallback in `query_log`.
4. If the environment needs a proxy, use the workspace/user-approved proxy setting; do not embed credentials in artifacts.

## Search strategy

- Break the brief into claim families: audience/context, domain facts, numbers, counterclaims, visual references, and implementation constraints.
- Search more than one engine/source type when stakes justify it.
- Use search results and snippets only to find candidate sources.
- Open and inspect the original source before using it as evidence.
- Prefer primary sources: standards, official documentation, original datasets, first-party reports, and research papers.
- Distinguish publication date from event/data date.
- Record contradictions rather than averaging them away.
- Stop when every important claim is supported or explicitly listed as a gap.

Set `research-bundle.mode` explicitly. Use `source-only` when approved supplied material is sufficient and `not-required` with a reason when no factual research is needed; never invent a search merely to satisfy a checklist.

## Failure handling

- A provider's HTTP success does not guarantee a successful result. Parse returned status/error fields.
- Retry only transient technical failures. A low-quality result is a research problem, not a technical fallback condition.
- If an explicit engine is requested and fails, report that failure; do not silently relabel another engine's result.
- Domain filters and date filters must be verified in returned sources, not assumed from CLI arguments.
- Never expose API keys in logs, prompts, manifests, screenshots, or final output.

## Minimum evidence package

`research-bundle.json` must include query history, opened sources, claim mapping, gaps, assumptions, and rejected sources. A slide may cite a claim ID only when that claim has at least one opened source ID.
