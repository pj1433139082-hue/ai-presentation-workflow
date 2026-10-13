"""Validation for the opt-in full-slide reconstruction profile.

These checks bind a declared page inventory to current concepts, source files,
and separate renders. They do not detect elements omitted from that inventory
or decide whether a reconstruction looks faithful.
"""

from __future__ import annotations

import base64
import hashlib
import json
import math
import posixpath
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET

try:
    import showcase_contract as _showcase
except ImportError:  # import when loaded as scripts.reconstruction_contract
    from . import showcase_contract as _showcase


RECONSTRUCTION_VERSION = "apw-reconstruction-v1"
RECONSTRUCTION_ROLES = {
    "background",
    "illustration",
    "connector",
    "arrow",
    "text",
    "special-typography",
    "decoration",
    "chart",
}

_CSS_URL_RE = re.compile(
    r"url\(\s*(?:(?P<quote>['\"])(?P<quoted>.*?)\1|(?P<bare>[^)]*?))\s*\)",
    re.IGNORECASE | re.DOTALL,
)
_CSS_IMPORT_RE = re.compile(r"@import\s+(?:url\(\s*)?(['\"])(.*?)\1\s*\)?", re.IGNORECASE | re.DOTALL)


class _RendererHTMLParser(HTMLParser):
    """Collect static HTML resource references and inline CSS declarations."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[tuple[str, str, str]] = []
        self.inline_css: list[str] = []
        self._in_style = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "style":
            self._in_style = True
        for name, value in attrs:
            if value is None:
                continue
            name = name.lower()
            if name in {"src", "href"}:
                self.references.append((tag, name, value.strip()))
            elif name == "style":
                self.inline_css.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "style":
            self._in_style = False

    def handle_data(self, data: str) -> None:
        if self._in_style:
            self.inline_css.append(data)


def _add_package_path(paths: set[str], value: Any) -> None:
    if isinstance(value, str) and value.strip():
        paths.add(Path(value).as_posix().casefold())


def _native_source_syntax(source_file: Path, source_path: Any, errors: list[str], location: str) -> None:
    """Parse source formats with known syntax while leaving other formats extensible."""
    suffix = Path(str(source_path)).suffix.casefold()
    try:
        if suffix == ".svg":
            root = ET.parse(source_file).getroot()
            local_name = root.tag.rsplit("}", 1)[-1] if isinstance(root.tag, str) else ""
            if local_name != "svg":
                errors.append(f"{location}: .svg source must have an SVG root element")
        elif suffix == ".xml":
            ET.parse(source_file)
        elif suffix == ".json":
            json.loads(source_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ET.ParseError, json.JSONDecodeError) as exc:
        errors.append(f"{location}: declared native source is not valid {suffix[1:].upper() or 'data'} ({exc})")


def _css_urls(text: str) -> list[str]:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    result: list[str] = []
    for match in _CSS_URL_RE.finditer(text):
        result.append((match.group("quoted") if match.group("quote") else match.group("bare") or "").strip())
    for match in _CSS_IMPORT_RE.finditer(text):
        result.append(match.group(2).strip())
    return result


def _check_renderer_reference(
    root: Path,
    owner_path: str,
    reference: str,
    *,
    tag: str,
    attribute: str,
    package_paths: set[str],
    concept_digests: set[str],
    errors: list[str],
    location: str,
) -> str | None:
    """Resolve one static URL and require local resources to be portable."""
    try:
        parsed = urlsplit(reference.strip())
    except ValueError as exc:
        errors.append(f"{location}: invalid static URL ({exc})")
        return None

    if parsed.scheme or parsed.netloc:
        if parsed.scheme.casefold() == "data":
            try:
                metadata, payload = reference.strip().split(",", 1)
                data = base64.b64decode(payload, validate=True) if ";base64" in metadata.casefold() else unquote(payload).encode("utf-8")
            except (ValueError, base64.binascii.Error):
                errors.append(f"{location}: invalid data URL")
                return None
            if hashlib.sha256(data).hexdigest().lower() in concept_digests:
                errors.append(f"{location}: a current full-page concept image cannot be embedded as a renderer resource")
            return None
        if attribute == "href" and tag in {"a", "area"} and parsed.scheme.casefold() in {"http", "https", "mailto", "tel"}:
            return None  # Explicit navigational links are not runtime dependencies.
        errors.append(f"{location}: external runtime resource is not portable for offline reconstruction")
        return None

    raw_path = unquote(parsed.path).replace("\\", "/")
    if not raw_path:
        return None  # Empty paths and same-document fragments need no file.
    if raw_path.startswith("/"):
        errors.append(f"{location}: absolute local resource paths are not portable")
        return None
    relative = posixpath.normpath(posixpath.join(posixpath.dirname(owner_path), raw_path))
    if relative in {"", "."} or relative == ".." or relative.startswith("../"):
        errors.append(f"{location}: local resource path must stay inside the project")
        return None

    safe_file = getattr(_showcase, "_safe_file", None)
    if not callable(safe_file):
        errors.append("showcase_contract._safe_file: required shared path validator is unavailable")
        return None
    resolved = safe_file(root, relative, errors, location)
    if resolved is None:
        return None
    if not (attribute == "href" and tag in {"a", "area"}) and _showcase._sha256_file(resolved).lower() in concept_digests:
        errors.append(f"{location}: a current full-page concept image cannot be embedded as a renderer resource")
        return None
    if Path(relative).as_posix().casefold() not in package_paths:
        errors.append(f"{location}: local resource must be a current concept, asset, native source, renderer, or declared map dependency to be exported")
        return None
    return Path(relative).as_posix()


def _validate_static_renderer_dependencies(
    root: Path,
    renderer_path: Any,
    renderer_file: Path | None,
    package_paths: set[str],
    concept_digests: set[str],
    errors: list[str],
    location: str,
) -> None:
    """Check static HTML src/href and CSS url/@import references for offline export."""
    if renderer_file is None or not isinstance(renderer_path, str):
        return
    if Path(renderer_path).suffix.casefold() not in {".html", ".htm", ".xhtml"}:
        return

    try:
        source = renderer_file.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        errors.append(f"{location}: renderer HTML is not readable UTF-8 ({exc})")
        return
    parser = _RendererHTMLParser()
    try:
        parser.feed(source)
        parser.close()
    except Exception as exc:  # HTMLParser is permissive; retain a clear failure if a custom parser rejects input.
        errors.append(f"{location}: renderer HTML could not be parsed ({exc})")
        return

    visited_css: set[str] = set()

    def inspect_css(css_path: str, css_file: Path) -> None:
        key = Path(css_path).as_posix().casefold()
        if key in visited_css:
            return
        visited_css.add(key)
        try:
            css = css_file.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            errors.append(f"{location}: CSS resource {css_path!r} is not readable UTF-8 ({exc})")
            return
        for index, url in enumerate(_css_urls(css)):
            ref_location = f"{location}: {css_path} CSS URL[{index}]"
            resolved_path = _check_renderer_reference(
                root, css_path, url, tag="style", attribute="url", package_paths=package_paths,
                concept_digests=concept_digests, errors=errors, location=ref_location,
            )
            if resolved_path and Path(resolved_path).suffix.casefold() == ".css":
                next_file = root / Path(*Path(resolved_path).parts)
                inspect_css(resolved_path, next_file)

    for tag, attribute, reference in parser.references:
        resolved_path = _check_renderer_reference(
            root, renderer_path, reference, tag=tag, attribute=attribute,
            package_paths=package_paths, concept_digests=concept_digests, errors=errors,
            location=f"{location} HTML <{tag}> {attribute}={reference!r}",
        )
        if resolved_path and Path(resolved_path).suffix.casefold() == ".css":
            inspect_css(resolved_path, root / Path(*Path(resolved_path).parts))
    for index, css in enumerate(parser.inline_css):
        for url_index, url in enumerate(_css_urls(css)):
            _check_renderer_reference(
                root, renderer_path, url, tag="style", attribute="url", package_paths=package_paths,
                concept_digests=concept_digests, errors=errors,
                location=f"{location} inline CSS[{index}] URL[{url_index}]",
            )


def _exact_keys(
    value: Any,
    required: set[str],
    location: str,
    errors: list[str],
    *,
    optional: set[str] | None = None,
) -> bool:
    if not isinstance(value, dict):
        errors.append(f"{location}: object required")
        return False
    optional = optional or set()
    missing = required - set(value)
    extra = set(value) - required - optional
    if missing:
        errors.append(f"{location}: missing fields {', '.join(sorted(missing))}")
    if extra:
        errors.append(f"{location}: unsupported fields {', '.join(sorted(extra))}")
    return not missing and not extra


def _number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _checked_file(root: Path, relative: Any, expected: Any, errors: list[str], location: str) -> Path | None:
    """Use showcase path/hash checks and reject in-project symlink components."""
    safe_file = getattr(_showcase, "_safe_file", None)
    digest_matches = getattr(_showcase, "_digest_matches", None)
    if not callable(safe_file) or not callable(digest_matches):
        errors.append("showcase_contract: shared safe-path and hash validators are unavailable")
        return None
    resolved = safe_file(root, relative, errors, location)
    if resolved is None:
        return None

    candidate = Path(relative)
    current = Path(root).resolve()
    for part in candidate.parts:
        if part in {"", "."}:
            continue
        current = current / part
        try:
            if current.is_symlink():
                errors.append(f"{location}: symbolic links are not allowed in reconstruction paths")
                return None
        except OSError:
            errors.append(f"{location}: cannot inspect path safety")
            return None

    return digest_matches(root, relative, expected, errors, location)


def _track_export_path(relative: Any, seen: dict[str, str], errors: list[str], location: str) -> None:
    if not isinstance(relative, str) or not relative.strip():
        return
    normalized = Path(relative).as_posix()
    key = normalized.casefold()
    previous = seen.get(key)
    if previous is not None and previous != normalized:
        errors.append(f"{location}: export path collides with {previous!r} on a case-insensitive filesystem")
    else:
        seen[key] = normalized


def _read_map(root: Path, profile: dict[str, Any], errors: list[str]) -> tuple[dict[str, Any] | None, Path | None]:
    location = "asset-manifest.json.reconstruction"
    _exact_keys(profile, {"contract_version", "map_path", "map_sha256"}, location, errors)
    if profile.get("contract_version") != RECONSTRUCTION_VERSION:
        errors.append(f"{location}.contract_version: must be {RECONSTRUCTION_VERSION!r}")
    map_path = _checked_file(root, profile.get("map_path"), profile.get("map_sha256"), errors, f"{location}.map_path")
    if map_path is None:
        return None, None
    try:
        value = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        errors.append(f"{location}.map_path: cannot read valid UTF-8 JSON ({exc})")
        return None, map_path
    if not isinstance(value, dict):
        errors.append("reconstruction map: top-level value must be an object")
        return None, map_path
    return value, map_path


def validate_full_slide_reconstruction(
    root: Path,
    brief: dict[str, Any],
    deck: dict[str, Any],
    manifest: dict[str, Any],
    errors: list[str],
    facts: dict[str, Any],
) -> None:
    """Validate the optional map and all declared source/render bindings."""
    root = Path(root)
    delivery = brief.get("delivery")
    asset_scope = delivery.get("asset_scope") if isinstance(delivery, dict) else None
    if asset_scope != "full-slide":
        errors.append("brief.json.delivery.asset_scope: reconstruction profile requires 'full-slide'")

    profile = manifest.get("reconstruction")
    if not isinstance(profile, dict):
        errors.append("asset-manifest.json.reconstruction: required object for full-slide scope")
        facts["reconstruction_status"] = "missing-contract"
        return

    map_doc, map_file = _read_map(root, profile, errors)
    if map_doc is None:
        facts["reconstruction_status"] = "invalid-map"
        return

    _exact_keys(map_doc, {"version", "canvas", "slides"}, "reconstruction map", errors, optional={"dependency_files"})
    if map_doc.get("version") != RECONSTRUCTION_VERSION:
        errors.append(f"reconstruction map.version: must be {RECONSTRUCTION_VERSION!r}")

    canvas = map_doc.get("canvas")
    if _exact_keys(canvas, {"width", "height"}, "reconstruction map.canvas", errors):
        width, height = canvas.get("width"), canvas.get("height")
        if not isinstance(width, int) or isinstance(width, bool) or width <= 0:
            errors.append("reconstruction map.canvas.width: positive finite integer required")
            canvas_width = None
        else:
            canvas_width = width
        if not isinstance(height, int) or isinstance(height, bool) or height <= 0:
            errors.append("reconstruction map.canvas.height: positive finite integer required")
            canvas_height = None
        else:
            canvas_height = height
    else:
        canvas_width, canvas_height = None, None

    keyed_rows = getattr(_showcase, "_keyed_rows", None)
    if not callable(keyed_rows):
        errors.append("showcase_contract._keyed_rows: required shared validator is unavailable")
        facts["reconstruction_status"] = "invalid-map"
        return
    deck_rows = keyed_rows(deck.get("slides"), "id", "deck-spec.json.slides", errors)
    map_slides = keyed_rows(map_doc.get("slides"), "slide_id", "reconstruction map.slides", errors)
    if not deck_rows:
        errors.append("deck-spec.json.slides: at least one slide is required for reconstruction")
    if set(map_slides) != set(deck_rows):
        errors.append("reconstruction map.slides: must cover every current deck slide exactly once")

    # A concept image remains the source reference, never a reconstruction
    # component under another role or a smaller placement box.
    concept_digests: set[str] = set()
    safe_file = getattr(_showcase, "_safe_file", None)
    if callable(safe_file):
        for slide_id, deck_slide in deck_rows.items():
            concept_source = safe_file(root, deck_slide.get("concept_path"), errors, f"deck-spec.json.slides[{slide_id}].concept_path")
            if concept_source is not None:
                concept_digests.add(_showcase._sha256_file(concept_source).lower())

    asset_rows = keyed_rows(manifest.get("assets"), "id", "asset-manifest.json.assets", errors)
    seen_paths: dict[str, str] = {}
    map_path = profile.get("map_path")
    _track_export_path(map_path, seen_paths, errors, "reconstruction map path")

    # Mirror the project-relative files that the exporter can actually carry.
    # A local HTML/CSS reference outside this set must be declared as a map
    # dependency or else it will silently disappear from the portable package.
    package_paths: set[str] = set()
    _add_package_path(package_paths, map_path)
    for name in (*getattr(_showcase, "CONCEPT_INPUT_DOCS", ()), "delivery-mode.json"):
        _add_package_path(package_paths, name)
    for asset in asset_rows.values():
        _add_package_path(package_paths, asset.get("path"))
        generation = asset.get("generation")
        if isinstance(generation, dict):
            _add_package_path(package_paths, generation.get("record_path"))
    for slide in map_doc.get("slides", []) if isinstance(map_doc.get("slides"), list) else []:
        if not isinstance(slide, dict):
            continue
        for key in ("concept_path", "render_path", "renderer_path"):
            _add_package_path(package_paths, slide.get(key))
        for item in slide.get("items", []) if isinstance(slide.get("items"), list) else []:
            if isinstance(item, dict) and item.get("representation") == "native":
                _add_package_path(package_paths, item.get("source_path"))
    dependencies = map_doc.get("dependency_files", [])
    if isinstance(dependencies, list):
        for dependency in dependencies:
            if isinstance(dependency, dict):
                _add_package_path(package_paths, dependency.get("path"))
    source_map = brief.get("source_map", [])
    if isinstance(source_map, list):
        for source in source_map:
            if isinstance(source, dict):
                _add_package_path(package_paths, source.get("path"))
    reference_doc = _showcase._load_json(root, "reference-study.json", [], required=False) if callable(getattr(_showcase, "_load_json", None)) else None
    selected_values = reference_doc.get("selected_reference_ids", []) if isinstance(reference_doc, dict) else []
    selected_references = {value for value in selected_values if isinstance(value, str)} if isinstance(selected_values, list) else set()
    if isinstance(reference_doc, dict) and isinstance(reference_doc.get("references"), list):
        for reference in reference_doc["references"]:
            if isinstance(reference, dict) and reference.get("id") in selected_references:
                _add_package_path(package_paths, reference.get("image_path"))
    provenance_root = root / "provenance"
    if provenance_root.is_dir():
        for provenance_file in provenance_root.rglob("*"):
            if provenance_file.is_file():
                _add_package_path(package_paths, provenance_file.relative_to(root).as_posix())

    used_assets: set[str] = set()
    review_outcomes: list[str] = []

    for asset_id, asset in asset_rows.items():
        _checked_file(root, asset.get("path"), asset.get("sha256"), errors, f"asset-manifest.json.assets[{asset_id}].path")
        _track_export_path(asset.get("path"), seen_paths, errors, f"asset-manifest.json.assets[{asset_id}].path")

    for slide_id, slide in map_slides.items():
        where = f"reconstruction map.slides[{slide_id}]"
        _exact_keys(
            slide,
            {"slide_id", "concept_path", "concept_sha256", "items", "render_path", "render_sha256", "renderer_path", "renderer_sha256", "review"},
            where,
            errors,
        )
        current_slide = deck_rows.get(slide_id, {})
        if slide.get("concept_path") != current_slide.get("concept_path"):
            errors.append(f"{where}.concept_path: must match the current deck concept")
        concept_file = _checked_file(root, slide.get("concept_path"), slide.get("concept_sha256"), errors, f"{where}.concept_path")
        concept_digest = None
        if concept_file is not None:
            concept_digest = _showcase._sha256_file(concept_file)
        _track_export_path(slide.get("concept_path"), seen_paths, errors, f"{where}.concept_path")

        render_file = _checked_file(root, slide.get("render_path"), slide.get("render_sha256"), errors, f"{where}.render_path")
        renderer_file = _checked_file(root, slide.get("renderer_path"), slide.get("renderer_sha256"), errors, f"{where}.renderer_path")
        _track_export_path(slide.get("render_path"), seen_paths, errors, f"{where}.render_path")
        _track_export_path(slide.get("renderer_path"), seen_paths, errors, f"{where}.renderer_path")
        render_digest = _showcase._sha256_file(render_file) if render_file is not None else None
        if render_file is not None and concept_file is not None and (
            render_file == concept_file or render_digest == concept_digest
        ):
            errors.append(f"{where}.render_path: reconstruction render must be a separate artifact from its concept")
        is_supported_image = getattr(_showcase, "_is_supported_image", None)
        if render_file is not None and callable(is_supported_image) and not is_supported_image(render_file):
            errors.append(f"{where}.render_path: must be a readable supported image for visual reinspection")

        items = slide.get("items")
        item_rows = keyed_rows(items, "id", f"{where}.items", errors)
        if not item_rows:
            errors.append(f"{where}.items: at least one inventoried item is required")
        background_seen = False
        for item_id, item in item_rows.items():
            item_where = f"{where}.items[{item_id}]"
            role = item.get("role")
            if not isinstance(role, str) or role not in RECONSTRUCTION_ROLES:
                errors.append(f"{item_where}.role: unsupported reconstruction role")
            if role == "background":
                background_seen = True
            bbox = item.get("bbox")
            if not isinstance(bbox, list) or len(bbox) != 4 or any(not _number(number) for number in bbox):
                errors.append(f"{item_where}.bbox: finite [x,y,w,h] geometry is required")
                bbox = None
            elif (
                bbox[0] < 0
                or bbox[1] < 0
                or bbox[2] <= 0
                or bbox[3] <= 0
                or (canvas_width is not None and bbox[0] + bbox[2] > canvas_width)
                or (canvas_height is not None and bbox[1] + bbox[3] > canvas_height)
            ):
                errors.append(f"{item_where}.bbox: positive geometry must remain inside the reconstruction canvas")
            if not _number(item.get("z")):
                errors.append(f"{item_where}.z: finite numeric stacking order is required")

            representation = item.get("representation")
            if representation == "asset":
                _exact_keys(item, {"id", "role", "bbox", "z", "representation", "asset_id"}, item_where, errors)
                asset_id_ref = item.get("asset_id")
                asset = asset_rows.get(asset_id_ref) if isinstance(asset_id_ref, str) else None
                if asset is None:
                    errors.append(f"{item_where}.asset_id: must identify a current asset-manifest row")
                elif asset.get("slide_id") != slide_id:
                    errors.append(f"{item_where}.asset_id: asset must belong to this slide")
                else:
                    used_assets.add(asset_id_ref)
                    if str(asset.get("sha256", "")).lower() in concept_digests:
                        errors.append(f"{item_where}.asset_id: a current full-page concept image cannot be reused as a reconstruction component")
            elif representation == "native":
                _exact_keys(item, {"id", "role", "bbox", "z", "representation", "source_path", "source_sha256"}, item_where, errors)
                source_path = item.get("source_path")
                source_file = _checked_file(root, source_path, item.get("source_sha256"), errors, f"{item_where}.source_path")
                _track_export_path(source_path, seen_paths, errors, f"{item_where}.source_path")
                if source_file is not None:
                    source_digest = _showcase._sha256_file(source_file).lower()
                    if source_digest in concept_digests:
                        errors.append(f"{item_where}.source_path: a current full-page concept image cannot be reused as a native reconstruction source")
                    _native_source_syntax(source_file, source_path, errors, f"{item_where}.source_path")
            else:
                errors.append(f"{item_where}.representation: must be 'asset' or 'native'")

        if not background_seen:
            errors.append(f"{where}.items: a background item must be accounted for")

        review = slide.get("review")
        _exact_keys(review, {"actor", "concept_sha256", "render_sha256", "coverage", "outcome", "user_acceptance"}, f"{where}.review", errors)
        if isinstance(review, dict):
            if review.get("actor") != "agent":
                errors.append(f"{where}.review.actor: must identify agent review metadata")
            if concept_digest is not None and str(review.get("concept_sha256", "")).lower() != concept_digest.lower():
                errors.append(f"{where}.review.concept_sha256: must bind the current concept")
            if render_digest is not None and str(review.get("render_sha256", "")).lower() != render_digest.lower():
                errors.append(f"{where}.review.render_sha256: must bind the current reconstruction render")
            if review.get("coverage") != "all-inventoried-elements":
                errors.append(f"{where}.review.coverage: must be 'all-inventoried-elements'")
            outcome = review.get("outcome")
            if not isinstance(outcome, str) or outcome not in {"agent-reviewed", "needs-repair"}:
                errors.append(f"{where}.review.outcome: must be 'agent-reviewed' or 'needs-repair'")
            else:
                review_outcomes.append(outcome)
            if outcome == "needs-repair":
                errors.append(f"{where}.review.outcome: needs-repair means full-slide delivery is incomplete")
            if review.get("user_acceptance") != "not-recorded":
                errors.append(f"{where}.review.user_acceptance: must remain 'not-recorded'")

        _validate_static_renderer_dependencies(
            root,
            slide.get("renderer_path"),
            renderer_file,
            package_paths,
            concept_digests,
            errors,
            f"{where}.renderer_path",
        )

    for asset_id in set(asset_rows) - used_assets:
        errors.append(f"asset-manifest.json.assets[{asset_id}]: asset row is not covered by a reconstruction-map item")

    dependencies = map_doc.get("dependency_files", [])
    if not isinstance(dependencies, list):
        errors.append("reconstruction map.dependency_files: must be a list when present")
    else:
        dependency_paths: set[str] = set()
        for index, dependency in enumerate(dependencies):
            where = f"reconstruction map.dependency_files[{index}]"
            _exact_keys(dependency, {"path", "sha256"}, where, errors)
            if not isinstance(dependency, dict):
                continue
            path = dependency.get("path")
            _checked_file(root, path, dependency.get("sha256"), errors, f"{where}.path")
            _track_export_path(path, seen_paths, errors, f"{where}.path")
            if isinstance(path, str):
                normalized = Path(path).as_posix().casefold()
                if normalized in dependency_paths:
                    errors.append(f"{where}.path: duplicate dependency path")
                dependency_paths.add(normalized)

    if map_file is not None:
        _track_export_path(map_path, seen_paths, errors, "reconstruction map path")
    facts["reconstruction_status"] = "agent-reviewed" if review_outcomes and all(value == "agent-reviewed" for value in review_outcomes) else "needs-repair-or-review"
    facts["reconstruction_review"] = "agent metadata; not proof of visual completeness or faithfulness"
    facts["reconstruction_user_acceptance"] = "not-recorded"
    facts["asset_coverage_scope"] = (
        "full-slide declared inventory with file and render bindings; machine checks cannot detect unlisted pixels "
        "or decide visual faithfulness"
    )
    facts["renderer_dependency_scope"] = (
        "static HTML src/href and CSS url/@import references must resolve to packaged files; "
        "exact current concept images embedded in these references are rejected; "
        "JavaScript imports and runtime-generated requests are not inspected"
    )


def reconstruction_artifact_paths(root: Path, manifest: dict[str, Any]) -> list[str]:
    """List the map and every declared reconstruction source for portable export."""
    errors: list[str] = []
    profile = manifest.get("reconstruction")
    if not isinstance(profile, dict):
        return []
    map_path = profile.get("map_path")
    map_file = _checked_file(root, map_path, profile.get("map_sha256"), errors, "asset-manifest.json.reconstruction.map_path")
    if map_file is None:
        raise ValueError("; ".join(errors) or "reconstruction map is missing or unsafe")
    try:
        map_doc = json.loads(map_file.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"reconstruction map cannot be read for export: {exc}") from exc
    if not isinstance(map_doc, dict) or not isinstance(map_doc.get("slides"), list):
        raise ValueError("reconstruction map slides are invalid for export")

    result: list[str] = [map_path]
    for slide in map_doc["slides"]:
        if not isinstance(slide, dict):
            raise ValueError("reconstruction map has an invalid slide for export")
        result.extend([slide.get("render_path"), slide.get("renderer_path")])
        items = slide.get("items")
        if not isinstance(items, list):
            raise ValueError("reconstruction map has invalid items for export")
        result.extend(
            item.get("source_path")
            for item in items
            if isinstance(item, dict) and item.get("representation") == "native"
        )
    dependencies = map_doc.get("dependency_files", [])
    if not isinstance(dependencies, list):
        raise ValueError("reconstruction map dependencies are invalid for export")
    result.extend(row.get("path") for row in dependencies if isinstance(row, dict))

    unique: list[str] = []
    seen: set[str] = set()
    for relative in result:
        if not isinstance(relative, str) or not relative.strip():
            raise ValueError("reconstruction map contains an invalid artifact path")
        key = Path(relative).as_posix().casefold()
        if key not in seen:
            seen.add(key)
            unique.append(relative)
    return unique


__all__ = [
    "RECONSTRUCTION_VERSION",
    "reconstruction_artifact_paths",
    "validate_full_slide_reconstruction",
]
