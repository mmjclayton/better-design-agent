"""
Design System Extractor.

Turns DOM data into a drop-in design-token system: CSS custom properties,
a Figma-compatible JSON export, and a Tailwind v3 theme.extend config.

Two strategies:
  - **direct**: the site already defines CSS custom properties. Use them
    verbatim (names + values).
  - **synthesised**: the site has no tokens. Synthesise names from
    usage-counted raw values (top colours → `--color-1..N`, etc.).

Pure data transformation — no LLM, no network. Caller fetches the DOM
and passes it in.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


SCHEMA_VERSION = 1

# Synthesised font-size scale, applied in ascending size order.
FONT_SIZE_SCALE = ["xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl"]


@dataclass
class Token:
    name: str
    value: str
    type: str  # color | dimension | string

    def css_line(self) -> str:
        return f"  {self.name}: {self.value};"

    def to_figma_dict(self) -> dict:
        return {"name": self.name, "value": self.value, "type": self.type}


@dataclass
class ExtractedSystem:
    strategy: str  # "direct" | "synthesised"
    source_url: str
    extracted_at: str
    colours: list[Token] = field(default_factory=list)
    typography: list[Token] = field(default_factory=list)
    spacing: list[Token] = field(default_factory=list)
    radius: list[Token] = field(default_factory=list)
    other: list[Token] = field(default_factory=list)

    @property
    def all_tokens(self) -> list[Token]:
        return (
            self.colours + self.typography + self.spacing
            + self.radius + self.other
        )

    @property
    def total_count(self) -> int:
        return len(self.all_tokens)

    def counts_by_category(self) -> dict[str, int]:
        return {
            "colours": len(self.colours),
            "typography": len(self.typography),
            "spacing": len(self.spacing),
            "radius": len(self.radius),
            "other": len(self.other),
        }


# ── Direct extraction from css_tokens ──


def _extract_direct(dom_data: dict, source_url: str) -> ExtractedSystem:
    tokens = dom_data.get("css_tokens", {}) or {}

    def _mk(entries: list[dict], type_: str) -> list[Token]:
        return [
            Token(name=e["name"], value=str(e["value"]).strip(), type=type_)
            for e in (entries or [])
            if e.get("name") and e.get("value")
        ]

    return ExtractedSystem(
        strategy="direct",
        source_url=source_url,
        extracted_at=datetime.now().isoformat(timespec="seconds"),
        colours=_mk(tokens.get("color", []), "color"),
        typography=_mk(tokens.get("font", []), "string"),
        spacing=_mk(tokens.get("spacing", []), "dimension"),
        radius=_mk(tokens.get("radius", []), "dimension"),
        other=_mk(tokens.get("other", []), "string"),
    )


# ── Synthesised extraction from usage-counted values ──


def _synthesise_colours(colors_text: list[dict], colors_bg: list[dict]) -> list[Token]:
    seen: set[str] = set()
    tokens: list[Token] = []
    # Text colours first, then backgrounds; preserve usage order.
    idx = 1
    for entry in list(colors_text) + list(colors_bg):
        raw = entry.get("color") or entry.get("value")
        if not raw or raw in seen:
            continue
        seen.add(raw)
        tokens.append(Token(name=f"--color-{idx}", value=str(raw), type="color"))
        idx += 1
        if idx > 24:
            break  # cap at 24 tokens
    return tokens


def _synthesise_font_families(families: list[dict]) -> list[Token]:
    tokens: list[Token] = []
    used_names: set[str] = set()
    idx = 1
    for entry in families:
        raw = entry.get("family") or entry.get("value")
        if not raw:
            continue
        lower = str(raw).lower()
        if "mono" in lower or "courier" in lower:
            name = "--font-mono"
        elif "serif" in lower and "sans" not in lower:
            name = "--font-serif"
        elif "sans" in lower or "inter" in lower or "arial" in lower or "helvetica" in lower:
            name = "--font-sans"
        else:
            name = f"--font-{idx}"
            idx += 1
        if name in used_names:
            continue
        used_names.add(name)
        tokens.append(Token(name=name, value=str(raw), type="string"))
    return tokens


def _parse_px(value: str) -> float | None:
    try:
        return float(value.replace("px", "").strip())
    except (ValueError, AttributeError):
        return None


def _synthesise_font_sizes(sizes: list[dict]) -> list[Token]:
    # Collect unique px values, sort ascending, map to the scale.
    values: list[tuple[float, str]] = []
    seen: set[str] = set()
    for entry in sizes:
        raw = entry.get("size") or entry.get("value")
        if not raw or raw in seen:
            continue
        seen.add(raw)
        px = _parse_px(str(raw))
        if px is not None:
            values.append((px, str(raw)))

    values.sort(key=lambda t: t[0])
    tokens: list[Token] = []
    for i, (_, raw) in enumerate(values[:len(FONT_SIZE_SCALE)]):
        tokens.append(Token(
            name=f"--font-size-{FONT_SIZE_SCALE[i]}",
            value=raw,
            type="dimension",
        ))
    return tokens


def _synthesise_spacing(spacing_values: list[dict]) -> list[Token]:
    # Unique values, sorted ascending by px, labelled 1..N.
    values: list[tuple[float, str]] = []
    seen: set[str] = set()
    for entry in spacing_values:
        raw = entry.get("value")
        if not raw or raw in seen:
            continue
        seen.add(raw)
        px = _parse_px(str(raw))
        if px is not None and px > 0:
            values.append((px, str(raw)))

    values.sort(key=lambda t: t[0])
    tokens: list[Token] = []
    for i, (_, raw) in enumerate(values[:12]):
        tokens.append(Token(name=f"--space-{i+1}", value=raw, type="dimension"))
    return tokens


def _extract_synthesised(dom_data: dict, source_url: str) -> ExtractedSystem:
    colors = dom_data.get("colors", {}) or {}
    fonts = dom_data.get("fonts", {}) or {}
    return ExtractedSystem(
        strategy="synthesised",
        source_url=source_url,
        extracted_at=datetime.now().isoformat(timespec="seconds"),
        colours=_synthesise_colours(
            colors.get("text", []), colors.get("background", []),
        ),
        typography=(
            _synthesise_font_families(fonts.get("families", []))
            + _synthesise_font_sizes(fonts.get("sizes", []))
        ),
        spacing=_synthesise_spacing(dom_data.get("spacing_values", [])),
        radius=[],
        other=[],
    )


def extract_system(dom_data: dict, source_url: str) -> ExtractedSystem:
    """Pick the best extraction strategy for the DOM and run it."""
    css_tokens = dom_data.get("css_tokens", {}) or {}
    has_any = any(
        css_tokens.get(cat) for cat in ("color", "font", "spacing", "radius")
    )
    if has_any:
        return _extract_direct(dom_data, source_url)
    return _extract_synthesised(dom_data, source_url)


# ── File writers ──


def _render_css_block(tokens: list[Token]) -> str:
    if not tokens:
        return ""
    body = "\n".join(t.css_line() for t in tokens)
    return f":root {{\n{body}\n}}\n"


def _render_tokens_css(system: ExtractedSystem) -> str:
    header = (
        f"/* Design tokens extracted from {system.source_url}\n"
        f" * Strategy: {system.strategy}\n"
        f" * Extracted: {system.extracted_at}\n"
        " */\n\n"
    )
    return header + _render_css_block(system.all_tokens)


def _render_colours_css(system: ExtractedSystem) -> str:
    return "/* Colour tokens */\n\n" + _render_css_block(system.colours)


def _render_typography_css(system: ExtractedSystem) -> str:
    return "/* Typography tokens */\n\n" + _render_css_block(system.typography)


def _render_spacing_css(system: ExtractedSystem) -> str:
    blocks = []
    if system.spacing:
        blocks.append("/* Spacing tokens */\n\n" + _render_css_block(system.spacing))
    if system.radius:
        blocks.append("\n/* Radius tokens */\n\n" + _render_css_block(system.radius))
    return "".join(blocks) or "/* No spacing tokens extracted */\n"


def _render_tokens_json(system: ExtractedSystem) -> str:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "source_url": system.source_url,
        "extracted_at": system.extracted_at,
        "strategy": system.strategy,
        "tokens": [t.to_figma_dict() for t in system.all_tokens],
    }
    return json.dumps(payload, indent=2)


def _render_tailwind_config(system: ExtractedSystem) -> str:
    # Map colour tokens to theme.extend.colors and spacing to theme.extend.spacing.
    # Strip leading -- from the var name for the Tailwind key.
    def _tw_key(var_name: str) -> str:
        return var_name.lstrip("-").removeprefix("color-").removeprefix("space-")

    color_lines = [
        f"        '{_tw_key(t.name)}': 'var({t.name})',"
        for t in system.colours
    ]
    space_lines = [
        f"        '{_tw_key(t.name)}': 'var({t.name})',"
        for t in system.spacing
    ]
    font_family_lines = [
        f"        '{_tw_key(t.name).removeprefix('font-')}': 'var({t.name})',"
        for t in system.typography if t.name.startswith("--font-") and "size" not in t.name
    ]

    return (
        f"// Tailwind v3 theme extension generated from {system.source_url}\n"
        "// Include these tokens via the CSS files in this directory, then\n"
        "// import this config from your tailwind.config.js.\n"
        "module.exports = {\n"
        "  theme: {\n"
        "    extend: {\n"
        "      colors: {\n"
        + "\n".join(color_lines)
        + "\n      },\n"
        "      spacing: {\n"
        + "\n".join(space_lines)
        + "\n      },\n"
        "      fontFamily: {\n"
        + "\n".join(font_family_lines)
        + "\n      },\n"
        "    },\n"
        "  },\n"
        "};\n"
    )


def _render_readme(system: ExtractedSystem) -> str:
    counts = system.counts_by_category()
    strategy_note = (
        "using the site's own CSS custom properties"
        if system.strategy == "direct"
        else "synthesised from usage-counted raw values"
    )
    return (
        "# Extracted Design System\n\n"
        f"**Source:** {system.source_url}\n"
        f"**Extracted:** {system.extracted_at}\n"
        f"**Strategy:** {system.strategy} ({strategy_note})\n\n"
        "## Token Counts\n\n"
        f"| Category | Count |\n"
        f"|----------|-------|\n"
        f"| Colours | {counts['colours']} |\n"
        f"| Typography | {counts['typography']} |\n"
        f"| Spacing | {counts['spacing']} |\n"
        f"| Radius | {counts['radius']} |\n"
        f"| Other | {counts['other']} |\n"
        f"| **Total** | **{system.total_count}** |\n\n"
        "## Files\n\n"
        "- `tokens.css` — all tokens in a single `:root` block\n"
        "- `colours.css` — colour tokens only\n"
        "- `typography.css` — font family + size tokens\n"
        "- `spacing.css` — spacing + radius tokens\n"
        "- `tokens.json` — Figma-Variables-compatible export\n"
        "- `tailwind.config.js` — Tailwind v3 theme.extend block\n\n"
        "## Usage\n\n"
        "```css\n"
        "/* In your main stylesheet */\n"
        "@import './tokens.css';\n\n"
        ".button { background: var(--color-1); padding: var(--space-2); }\n"
        "```\n\n"
        "_Tokens extracted by design-intel. Names from 'synthesised' runs are "
        "mechanical — rename them to match your team's conventions before "
        "shipping._\n"
    )


@dataclass
class WriteResult:
    output_dir: Path
    files_written: list[Path]
    counts: dict[str, int]
    strategy: str

    def to_json(self) -> str:
        return json.dumps({
            "output_dir": str(self.output_dir),
            "files_written": [str(p) for p in self.files_written],
            "counts": self.counts,
            "strategy": self.strategy,
            "total": sum(self.counts.values()),
        }, indent=2)


def write_system_to_dir(
    system: ExtractedSystem, output_dir: Path,
) -> WriteResult:
    """Write all six (or seven) files to the output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    files = [
        ("tokens.css", _render_tokens_css(system)),
        ("colours.css", _render_colours_css(system)),
        ("typography.css", _render_typography_css(system)),
        ("spacing.css", _render_spacing_css(system)),
        ("tokens.json", _render_tokens_json(system)),
        ("README.md", _render_readme(system)),
    ]
    if system.colours or system.spacing:
        files.append(("tailwind.config.js", _render_tailwind_config(system)))

    for name, content in files:
        path = output_dir / name
        path.write_text(content)
        written.append(path)

    return WriteResult(
        output_dir=output_dir,
        files_written=written,
        counts=system.counts_by_category(),
        strategy=system.strategy,
    )
