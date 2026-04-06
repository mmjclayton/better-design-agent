"""
Style Guide extraction and comparison.

Captures a comprehensive design profile from a live URL — colours, typography,
spacing, buttons, forms, links, cards, headings, images, borders, shadows,
transitions.  Saves as a YAML style guide that can later be used as a
comparison target for ui-audit.

Pure data transformation — no LLM.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


SCHEMA_VERSION = 1
DEFAULT_GUIDE_DIR = Path(".design-intel/guides")


# ── Data model ──


@dataclass
class ElementStyle:
    """Computed style snapshot for a single UI element."""
    selector: str = ""
    color: str | None = None
    bg: str | None = None
    font_size: str | None = None
    font_weight: str | None = None
    font_family: str | None = None
    line_height: str | None = None
    letter_spacing: str | None = None
    text_transform: str | None = None
    padding: str | None = None
    border_radius: str | None = None
    border: str | None = None
    box_shadow: str | None = None
    transition: str | None = None
    cursor: str | None = None
    height: int | None = None
    width: int | None = None
    gap: str | None = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}

    @classmethod
    def from_dict(cls, d: dict) -> ElementStyle:
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid_fields})


@dataclass
class StyleGuide:
    """Comprehensive design profile extracted from a reference site."""
    schema_version: int = SCHEMA_VERSION
    name: str = ""
    source_url: str = ""
    extracted_at: str = ""

    # Global tokens
    colors_text: list[dict] = field(default_factory=list)       # [{color, count}]
    colors_background: list[dict] = field(default_factory=list)  # [{color, count}]
    font_families: list[dict] = field(default_factory=list)      # [{family, count}]
    font_sizes: list[dict] = field(default_factory=list)         # [{size, count}]
    spacing_values: list[dict] = field(default_factory=list)     # [{value, count}]
    css_tokens: dict = field(default_factory=dict)

    # Layout
    body_font_size: str | None = None
    body_line_height: str | None = None
    body_font_family: str | None = None
    body_bg: str | None = None

    # Component styles
    buttons: list[dict] = field(default_factory=list)
    inputs: list[dict] = field(default_factory=list)
    links: list[dict] = field(default_factory=list)
    cards: list[dict] = field(default_factory=list)
    headings: list[dict] = field(default_factory=list)
    images: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "name": self.name,
            "source_url": self.source_url,
            "extracted_at": self.extracted_at,
            "global": {
                "colors_text": self.colors_text,
                "colors_background": self.colors_background,
                "font_families": self.font_families,
                "font_sizes": self.font_sizes,
                "spacing_values": self.spacing_values,
                "css_tokens": self.css_tokens,
            },
            "layout": {
                "body_font_size": self.body_font_size,
                "body_line_height": self.body_line_height,
                "body_font_family": self.body_font_family,
                "body_bg": self.body_bg,
            },
            "components": {
                "buttons": self.buttons,
                "inputs": self.inputs,
                "links": self.links,
                "cards": self.cards,
                "headings": self.headings,
                "images": self.images,
            },
        }

    @classmethod
    def from_dict(cls, d: dict) -> StyleGuide:
        g = d.get("global", {})
        lay = d.get("layout", {})
        comp = d.get("components", {})
        return cls(
            schema_version=d.get("schema_version", SCHEMA_VERSION),
            name=d.get("name", ""),
            source_url=d.get("source_url", ""),
            extracted_at=d.get("extracted_at", ""),
            colors_text=g.get("colors_text", []),
            colors_background=g.get("colors_background", []),
            font_families=g.get("font_families", []),
            font_sizes=g.get("font_sizes", []),
            spacing_values=g.get("spacing_values", []),
            css_tokens=g.get("css_tokens", {}),
            body_font_size=lay.get("body_font_size"),
            body_line_height=lay.get("body_line_height"),
            body_font_family=lay.get("body_font_family"),
            body_bg=lay.get("body_bg"),
            buttons=comp.get("buttons", []),
            inputs=comp.get("inputs", []),
            links=comp.get("links", []),
            cards=comp.get("cards", []),
            headings=comp.get("headings", []),
            images=comp.get("images", []),
        )

    def to_yaml(self) -> str:
        return yaml.dump(self.to_dict(), default_flow_style=False, sort_keys=False)

    def to_markdown(self) -> str:
        lines = [
            f"## Style Guide: {self.name}\n",
            f"Source: {self.source_url}",
            f"Extracted: {self.extracted_at}\n",
        ]

        # Colors
        if self.colors_text or self.colors_background:
            lines.append("### Colors\n")
            if self.colors_text:
                lines.append("**Text colors:**")
                for c in self.colors_text[:8]:
                    lines.append(f"- `{c['color']}` ({c['count']}x)")
            if self.colors_background:
                lines.append("\n**Background colors:**")
                for c in self.colors_background[:8]:
                    lines.append(f"- `{c['color']}` ({c['count']}x)")
            lines.append("")

        # Typography
        if self.font_families or self.font_sizes:
            lines.append("### Typography\n")
            if self.body_font_family:
                lines.append(f"Body: {self.body_font_family} {self.body_font_size}/{self.body_line_height}")
            if self.font_families:
                lines.append(f"Families: {', '.join(f['family'] for f in self.font_families[:4])}")
            if self.font_sizes:
                lines.append(f"Scale: {', '.join(s['size'] for s in self.font_sizes[:10])}")
            lines.append("")

        # Spacing
        if self.spacing_values:
            lines.append("### Spacing\n")
            lines.append(f"Values: {', '.join(s['value'] for s in self.spacing_values[:10])}")
            lines.append("")

        # Components
        for comp_name, comp_list in [
            ("Buttons", self.buttons),
            ("Form inputs", self.inputs),
            ("Links", self.links),
            ("Cards", self.cards),
            ("Headings", self.headings),
        ]:
            if comp_list:
                lines.append(f"### {comp_name}\n")
                for i, item in enumerate(comp_list[:5]):
                    label = item.get("text", item.get("selector", f"#{i+1}"))[:30]
                    lines.append(f"**{label}**")
                    for key in ["bg", "color", "font_size", "font_weight", "padding",
                                "border_radius", "border", "box_shadow", "transition"]:
                        if item.get(key):
                            lines.append(f"- {key}: `{item[key]}`")
                    lines.append("")

        return "\n".join(lines)


# ── Extraction ──


def extract_style_guide(dom_data: dict, url: str, name: str) -> StyleGuide:
    """Extract a comprehensive style guide from DOM data."""
    colors = dom_data.get("colors", {}) or {}
    fonts = dom_data.get("fonts", {}) or {}
    layout = dom_data.get("layout", {}) or {}
    comp_styles = dom_data.get("component_styles", {}) or {}
    spacing = dom_data.get("spacing_values", []) or []
    tokens = dom_data.get("css_tokens", {}) or {}

    return StyleGuide(
        name=name,
        source_url=url,
        extracted_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        colors_text=colors.get("text", []),
        colors_background=colors.get("background", []),
        font_families=fonts.get("families", []),
        font_sizes=fonts.get("sizes", []),
        spacing_values=spacing,
        css_tokens=tokens,
        body_font_size=layout.get("body_font_size"),
        body_line_height=layout.get("body_line_height"),
        body_font_family=layout.get("body_font_family"),
        body_bg=layout.get("body_bg"),
        buttons=comp_styles.get("buttons", []),
        inputs=comp_styles.get("inputs", []),
        links=comp_styles.get("links", []),
        cards=comp_styles.get("cards", []),
        headings=comp_styles.get("headings", []),
        images=comp_styles.get("images", []),
    )


# ── Persistence ──


def save_guide(guide: StyleGuide, directory: Path | None = None) -> Path:
    """Save a style guide as YAML. Returns the file path."""
    guide_dir = directory or DEFAULT_GUIDE_DIR
    guide_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{guide.name}.yaml"
    path = guide_dir / filename
    path.write_text(guide.to_yaml())
    return path


def load_guide(path: Path) -> StyleGuide:
    """Load a style guide from a YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Style guide not found: {path}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"Invalid style guide format: {path}")
    return StyleGuide.from_dict(data)


def list_guides(directory: Path | None = None) -> list[Path]:
    """List all saved style guides."""
    guide_dir = directory or DEFAULT_GUIDE_DIR
    if not guide_dir.exists():
        return []
    return sorted(guide_dir.glob("*.yaml"))


def resolve_guide(name_or_path: str, directory: Path | None = None) -> Path:
    """Resolve a guide name or path to a file path."""
    # Try as direct path first
    direct = Path(name_or_path)
    if direct.exists():
        return direct

    # Try as name in guide directory
    guide_dir = directory or DEFAULT_GUIDE_DIR
    by_name = guide_dir / f"{name_or_path}.yaml"
    if by_name.exists():
        return by_name

    # Try with .yaml extension
    if not name_or_path.endswith(".yaml"):
        with_ext = guide_dir / f"{name_or_path}.yaml"
        if with_ext.exists():
            return with_ext

    raise FileNotFoundError(
        f"Style guide '{name_or_path}' not found. "
        f"Looked in: {direct}, {by_name}"
    )


# ── Comparison engine ──


def _parse_px(value: str | None) -> float | None:
    if not value:
        return None
    v = value.strip().lower()
    if v.endswith("px"):
        try:
            return float(v[:-2])
        except ValueError:
            return None
    return None


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int] | None:
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = h[0]*2 + h[1]*2 + h[2]*2
    if len(h) != 6:
        return None
    try:
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
    except ValueError:
        return None


def _color_distance(c1: str, c2: str) -> float | None:
    """Distance between two hex colours in RGB space."""
    rgb1 = _hex_to_rgb(c1)
    rgb2 = _hex_to_rgb(c2)
    if not rgb1 or not rgb2:
        return None
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(rgb1, rgb2)))


def _find_closest_color(target: str, palette: list[str]) -> tuple[str | None, float]:
    """Find the closest colour in a palette to the target."""
    best_match = None
    best_dist = float("inf")
    for c in palette:
        dist = _color_distance(target, c)
        if dist is not None and dist < best_dist:
            best_dist = dist
            best_match = c
    return best_match, best_dist


def _size_distance(actual: str | None, reference: str | None) -> float | None:
    """Absolute px difference between two size values."""
    a = _parse_px(actual)
    b = _parse_px(reference)
    if a is None or b is None:
        return None
    return abs(a - b)


@dataclass
class ComparisonFinding:
    category: str
    element: str
    property: str
    actual: str
    reference: str
    distance: float  # 0.0 = perfect match
    severity: str  # "match", "close", "different"

    def to_dict(self) -> dict:
        return self.__dict__


@dataclass
class GuideComparison:
    """Result of comparing a site against a style guide."""
    guide_name: str
    guide_source: str
    findings: list[ComparisonFinding] = field(default_factory=list)
    category_scores: dict[str, float] = field(default_factory=dict)

    @property
    def overall_match(self) -> float:
        if not self.category_scores:
            return 0.0
        return round(sum(self.category_scores.values()) / len(self.category_scores), 1)

    def to_dict(self) -> dict:
        return {
            "guide_name": self.guide_name,
            "guide_source": self.guide_source,
            "overall_match": self.overall_match,
            "category_scores": self.category_scores,
            "findings": [f.to_dict() for f in self.findings],
        }

    def to_markdown(self) -> str:
        lines = [
            f"## Style Guide Comparison: vs {self.guide_name}\n",
            f"Reference: {self.guide_source}\n",
            f"**Overall match: {self.overall_match}%**\n",
        ]

        # Category scores table
        lines.append("| Category | Match |")
        lines.append("|----------|-------|")
        for cat, score in sorted(self.category_scores.items(), key=lambda x: x[1]):
            bar = _match_bar(score)
            lines.append(f"| {cat.replace('_', ' ').title()} | {score:.0f}% {bar} |")
        lines.append("")

        # Group findings by category
        by_cat: dict[str, list[ComparisonFinding]] = {}
        for f in self.findings:
            by_cat.setdefault(f.category, []).append(f)

        for cat, cat_findings in by_cat.items():
            different = [f for f in cat_findings if f.severity == "different"]
            if not different:
                continue
            lines.append(f"### {cat.replace('_', ' ').title()} — differences\n")
            for f in different[:10]:
                lines.append(
                    f"- **{f.element}** `{f.property}`: "
                    f"yours=`{f.actual}` reference=`{f.reference}`"
                )
            lines.append("")

        return "\n".join(lines)


def _match_bar(pct: float) -> str:
    """Simple text bar for match percentage."""
    filled = round(pct / 10)
    return "[" + "#" * filled + "." * (10 - filled) + "]"


# ── Comparison logic ──


def compare_against_guide(dom_data: dict, guide: StyleGuide) -> GuideComparison:
    """Compare a site's DOM data against a style guide.

    Returns distance-based scores (0-100, higher = closer match) for each
    category.
    """
    findings: list[ComparisonFinding] = []
    category_scores: dict[str, float] = {}

    # ── Colors ──
    colors = dom_data.get("colors", {}) or {}
    actual_text = [c["color"] for c in colors.get("text", [])]
    ref_text = [c["color"] for c in guide.colors_text]
    actual_bg = [c["color"] for c in colors.get("background", [])]
    ref_bg = [c["color"] for c in guide.colors_background]

    color_matches = 0
    color_total = 0

    for actual_c in actual_text[:8]:
        closest, dist = _find_closest_color(actual_c, ref_text)
        color_total += 1
        severity = "match" if dist < 10 else "close" if dist < 40 else "different"
        if dist < 40:
            color_matches += 1
        findings.append(ComparisonFinding(
            category="colors", element="text", property="color",
            actual=actual_c, reference=closest or "—",
            distance=dist, severity=severity,
        ))

    for actual_c in actual_bg[:6]:
        closest, dist = _find_closest_color(actual_c, ref_bg)
        color_total += 1
        severity = "match" if dist < 10 else "close" if dist < 40 else "different"
        if dist < 40:
            color_matches += 1
        findings.append(ComparisonFinding(
            category="colors", element="background", property="color",
            actual=actual_c, reference=closest or "—",
            distance=dist, severity=severity,
        ))

    category_scores["colors"] = round(color_matches / max(color_total, 1) * 100, 1)

    # ── Typography ──
    fonts = dom_data.get("fonts", {}) or {}
    actual_families = [f["family"].lower() for f in fonts.get("families", [])]
    ref_families = [f["family"].lower() for f in guide.font_families]
    actual_sizes = [s["size"] for s in fonts.get("sizes", [])]
    ref_sizes = [s["size"] for s in guide.font_sizes]

    typo_matches = 0
    typo_total = 0

    # Family match
    for af in actual_families[:3]:
        typo_total += 1
        if af in ref_families:
            typo_matches += 1
            findings.append(ComparisonFinding(
                category="typography", element="global", property="font-family",
                actual=af, reference=af, distance=0, severity="match",
            ))
        else:
            findings.append(ComparisonFinding(
                category="typography", element="global", property="font-family",
                actual=af, reference=ref_families[0] if ref_families else "—",
                distance=100, severity="different",
            ))

    # Size match
    ref_sizes_px = [_parse_px(s) for s in ref_sizes]
    ref_sizes_px = [s for s in ref_sizes_px if s is not None]
    for actual_s in actual_sizes[:8]:
        actual_px = _parse_px(actual_s)
        if actual_px is None:
            continue
        typo_total += 1
        # Find closest reference size
        if ref_sizes_px:
            closest_px = min(ref_sizes_px, key=lambda r: abs(r - actual_px))
            dist = abs(actual_px - closest_px)
            severity = "match" if dist < 1 else "close" if dist < 3 else "different"
            if dist < 3:
                typo_matches += 1
            findings.append(ComparisonFinding(
                category="typography", element="global", property="font-size",
                actual=actual_s, reference=f"{closest_px}px",
                distance=dist, severity=severity,
            ))

    category_scores["typography"] = round(typo_matches / max(typo_total, 1) * 100, 1)

    # ── Spacing ──
    actual_spacing = dom_data.get("spacing_values", []) or []
    ref_spacing_px = [_parse_px(s["value"]) for s in guide.spacing_values]
    ref_spacing_px = [s for s in ref_spacing_px if s is not None]

    space_matches = 0
    space_total = 0
    for s in actual_spacing[:12]:
        actual_px = _parse_px(s.get("value", ""))
        if actual_px is None:
            continue
        space_total += 1
        if ref_spacing_px:
            closest_px = min(ref_spacing_px, key=lambda r: abs(r - actual_px))
            dist = abs(actual_px - closest_px)
            severity = "match" if dist < 1 else "close" if dist < 4 else "different"
            if dist < 4:
                space_matches += 1

    category_scores["spacing"] = round(space_matches / max(space_total, 1) * 100, 1)

    # ── Component comparisons ──
    comp_styles = dom_data.get("component_styles", {}) or {}

    for comp_name, ref_list in [
        ("buttons", guide.buttons),
        ("inputs", guide.inputs),
        ("links", guide.links),
        ("cards", guide.cards),
    ]:
        actual_list = comp_styles.get(comp_name, [])
        if not ref_list or not actual_list:
            continue

        comp_matches = 0
        comp_total = 0

        # Compare each actual element against the reference "average"
        # Use the first reference element as the canonical style
        ref = ref_list[0]

        for actual in actual_list[:5]:
            for prop in ["bg", "color", "font_size", "border_radius", "padding", "border", "box_shadow"]:
                actual_val = actual.get(prop)
                ref_val = ref.get(prop)
                if actual_val is None and ref_val is None:
                    continue
                if actual_val is None or ref_val is None:
                    comp_total += 1
                    findings.append(ComparisonFinding(
                        category=comp_name, element=actual.get("selector", "?"),
                        property=prop,
                        actual=str(actual_val or "none"),
                        reference=str(ref_val or "none"),
                        distance=100, severity="different",
                    ))
                    continue

                comp_total += 1

                # Color properties
                if prop in ("bg", "color") and actual_val.startswith("#") and ref_val.startswith("#"):
                    dist = _color_distance(actual_val, ref_val)
                    if dist is not None:
                        severity = "match" if dist < 15 else "close" if dist < 50 else "different"
                        if dist < 50:
                            comp_matches += 1
                        if severity == "different":
                            findings.append(ComparisonFinding(
                                category=comp_name, element=actual.get("selector", "?"),
                                property=prop,
                                actual=actual_val, reference=ref_val,
                                distance=dist, severity=severity,
                            ))
                        continue

                # Size properties
                if prop in ("font_size", "border_radius", "padding"):
                    a_px = _parse_px(str(actual_val))
                    r_px = _parse_px(str(ref_val))
                    if a_px is not None and r_px is not None:
                        dist = abs(a_px - r_px)
                        severity = "match" if dist < 1 else "close" if dist < 4 else "different"
                        if dist < 4:
                            comp_matches += 1
                        if severity == "different":
                            findings.append(ComparisonFinding(
                                category=comp_name, element=actual.get("selector", "?"),
                                property=prop,
                                actual=str(actual_val), reference=str(ref_val),
                                distance=dist, severity=severity,
                            ))
                        continue

                # String equality for everything else
                if str(actual_val).strip() == str(ref_val).strip():
                    comp_matches += 1
                else:
                    findings.append(ComparisonFinding(
                        category=comp_name, element=actual.get("selector", "?"),
                        property=prop,
                        actual=str(actual_val), reference=str(ref_val),
                        distance=100, severity="different",
                    ))

        if comp_total > 0:
            category_scores[comp_name] = round(comp_matches / comp_total * 100, 1)

    # ── Headings ──
    actual_headings = comp_styles.get("headings", [])
    if guide.headings and actual_headings:
        heading_matches = 0
        heading_total = 0
        # Group by heading level and compare
        ref_by_tag: dict[str, dict] = {}
        for h in guide.headings:
            tag = h.get("selector", "").split(".")[0]
            if tag and tag not in ref_by_tag:
                ref_by_tag[tag] = h

        for actual in actual_headings[:6]:
            tag = actual.get("selector", "").split(".")[0]
            ref_h = ref_by_tag.get(tag)
            if not ref_h:
                continue
            for prop in ["font_size", "font_weight", "color", "letter_spacing", "text_transform"]:
                actual_val = actual.get(prop)
                ref_val = ref_h.get(prop)
                if actual_val is None and ref_val is None:
                    continue
                heading_total += 1
                if actual_val == ref_val:
                    heading_matches += 1
                elif prop == "font_size":
                    dist = _size_distance(str(actual_val), str(ref_val))
                    if dist is not None and dist < 3:
                        heading_matches += 1
                    elif dist is not None:
                        findings.append(ComparisonFinding(
                            category="headings", element=tag,
                            property=prop,
                            actual=str(actual_val), reference=str(ref_val),
                            distance=dist, severity="different",
                        ))
                elif prop == "color" and actual_val and ref_val:
                    dist = _color_distance(str(actual_val), str(ref_val))
                    if dist is not None and dist < 50:
                        heading_matches += 1

        if heading_total > 0:
            category_scores["headings"] = round(heading_matches / heading_total * 100, 1)

    return GuideComparison(
        guide_name=guide.name,
        guide_source=guide.source_url,
        findings=findings,
        category_scores=category_scores,
    )
