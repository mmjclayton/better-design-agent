"""Tests for the design system extractor."""

import json

from src.analysis.system_extractor import (
    FONT_SIZE_SCALE,
    SCHEMA_VERSION,
    Token,
    extract_system,
    write_system_to_dir,
    _synthesise_colours,
    _synthesise_font_families,
    _synthesise_font_sizes,
    _synthesise_spacing,
)


# ── Strategy selection ──


def test_direct_strategy_when_css_tokens_exist():
    dom = {"css_tokens": {
        "color": [{"name": "--brand-primary", "value": "#ff6600"}],
        "spacing": [], "font": [], "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    assert system.strategy == "direct"
    assert len(system.colours) == 1
    assert system.colours[0].name == "--brand-primary"
    assert system.colours[0].value == "#ff6600"


def test_synthesised_strategy_when_no_css_tokens():
    dom = {
        "css_tokens": {"color": [], "spacing": [], "font": [], "radius": [], "other": []},
        "colors": {"text": [{"color": "#111", "count": 100}], "background": []},
        "fonts": {"families": [{"family": "Inter, sans-serif", "count": 50}], "sizes": []},
        "spacing_values": [],
    }
    system = extract_system(dom, "https://x.com")
    assert system.strategy == "synthesised"
    assert len(system.colours) == 1
    assert system.colours[0].name == "--color-1"


def test_direct_preferred_even_when_raw_data_present():
    dom = {
        "css_tokens": {
            "color": [{"name": "--brand", "value": "#000"}],
            "spacing": [], "font": [], "radius": [], "other": [],
        },
        "colors": {"text": [{"color": "#fff"}], "background": []},
    }
    system = extract_system(dom, "https://x.com")
    assert system.strategy == "direct"


# ── Direct extraction ──


def test_direct_extraction_preserves_token_names():
    dom = {"css_tokens": {
        "color": [
            {"name": "--primary", "value": "#ff6600"},
            {"name": "--secondary", "value": "#0066ff"},
        ],
        "font": [{"name": "--font-sans", "value": "Inter, sans-serif"}],
        "spacing": [{"name": "--space-sm", "value": "8px"}],
        "radius": [{"name": "--radius-md", "value": "8px"}],
        "other": [{"name": "--shadow-sm", "value": "0 1px 2px rgba(0,0,0,0.1)"}],
    }}
    system = extract_system(dom, "https://x.com")
    assert len(system.colours) == 2
    assert len(system.typography) == 1
    assert len(system.spacing) == 1
    assert len(system.radius) == 1
    assert len(system.other) == 1


def test_direct_extraction_skips_empty_entries():
    dom = {"css_tokens": {
        "color": [
            {"name": "--primary", "value": "#ff6600"},
            {"name": "", "value": "bad"},
            {"name": "--secondary", "value": ""},
        ],
        "spacing": [], "font": [], "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    assert len(system.colours) == 1


def test_direct_extraction_assigns_types():
    dom = {"css_tokens": {
        "color": [{"name": "--c", "value": "#000"}],
        "spacing": [{"name": "--s", "value": "8px"}],
        "font": [{"name": "--f", "value": "Inter"}],
        "radius": [{"name": "--r", "value": "4px"}],
        "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    assert system.colours[0].type == "color"
    assert system.spacing[0].type == "dimension"
    assert system.radius[0].type == "dimension"
    assert system.typography[0].type == "string"


# ── Synthesis: colours ──


def test_synthesise_colours_numbers_tokens_in_usage_order():
    text = [{"color": "#111", "count": 100}, {"color": "#333", "count": 50}]
    bg = [{"color": "#fff", "count": 200}]
    tokens = _synthesise_colours(text, bg)
    assert [t.name for t in tokens] == ["--color-1", "--color-2", "--color-3"]
    assert tokens[0].value == "#111"
    assert tokens[2].value == "#fff"


def test_synthesise_colours_dedupes_across_text_and_bg():
    text = [{"color": "#111"}, {"color": "#fff"}]
    bg = [{"color": "#fff"}, {"color": "#eee"}]
    tokens = _synthesise_colours(text, bg)
    values = [t.value for t in tokens]
    assert values == ["#111", "#fff", "#eee"]


def test_synthesise_colours_caps_at_24():
    text = [{"color": f"#{i:06x}"} for i in range(50)]
    tokens = _synthesise_colours(text, [])
    assert len(tokens) == 24


# ── Synthesis: fonts ──


def test_synthesise_font_families_assigns_semantic_names():
    families = [
        {"family": "Inter, sans-serif"},
        {"family": "Georgia, serif"},
        {"family": "Menlo, monospace"},
    ]
    tokens = _synthesise_font_families(families)
    names = [t.name for t in tokens]
    assert "--font-sans" in names
    assert "--font-serif" in names
    assert "--font-mono" in names


def test_synthesise_font_families_falls_back_to_numeric():
    families = [{"family": "Custom Display"}, {"family": "Weird Thing"}]
    tokens = _synthesise_font_families(families)
    # Both fall through to numeric naming
    names = [t.name for t in tokens]
    assert "--font-1" in names
    assert "--font-2" in names


def test_synthesise_font_families_deduplicates_by_name():
    families = [
        {"family": "Inter, sans-serif"},
        {"family": "Helvetica, sans-serif"},  # also maps to --font-sans
    ]
    tokens = _synthesise_font_families(families)
    # Only the first --font-sans is kept
    sans_tokens = [t for t in tokens if t.name == "--font-sans"]
    assert len(sans_tokens) == 1


def test_synthesise_font_sizes_sorts_ascending_and_maps_to_scale():
    sizes = [
        {"size": "24px"}, {"size": "14px"}, {"size": "18px"},
        {"size": "12px"}, {"size": "16px"},
    ]
    tokens = _synthesise_font_sizes(sizes)
    # Expect tokens in ascending order: xs=12, sm=14, base=16, lg=18, xl=24
    assert len(tokens) == 5
    assert tokens[0].name == "--font-size-xs"
    assert tokens[0].value == "12px"
    assert tokens[-1].name == "--font-size-xl"
    assert tokens[-1].value == "24px"


def test_synthesise_font_sizes_caps_at_scale_length():
    sizes = [{"size": f"{i}px"} for i in range(10, 30)]
    tokens = _synthesise_font_sizes(sizes)
    assert len(tokens) == len(FONT_SIZE_SCALE)


# ── Synthesis: spacing ──


def test_synthesise_spacing_sorts_ascending_and_labels_numerically():
    values = [
        {"value": "24px"}, {"value": "8px"}, {"value": "16px"}, {"value": "4px"},
    ]
    tokens = _synthesise_spacing(values)
    assert [t.name for t in tokens] == ["--space-1", "--space-2", "--space-3", "--space-4"]
    assert tokens[0].value == "4px"
    assert tokens[-1].value == "24px"


def test_synthesise_spacing_caps_at_12_and_skips_zero():
    values = [{"value": "0px"}] + [{"value": f"{i*4}px"} for i in range(1, 20)]
    tokens = _synthesise_spacing(values)
    assert len(tokens) == 12
    assert all(t.value != "0px" for t in tokens)


# ── File output ──


def test_write_system_creates_all_files(tmp_path):
    dom = {"css_tokens": {
        "color": [{"name": "--brand", "value": "#ff0000"}],
        "spacing": [{"name": "--s", "value": "8px"}],
        "font": [{"name": "--font-sans", "value": "Inter"}],
        "radius": [{"name": "--r", "value": "4px"}],
        "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")

    expected = {
        "tokens.css", "colours.css", "typography.css",
        "spacing.css", "tokens.json", "README.md", "tailwind.config.js",
    }
    actual = {p.name for p in result.files_written}
    assert expected == actual
    for path in result.files_written:
        assert path.exists()
        assert path.read_text()  # non-empty


def test_tokens_css_contains_all_tokens_in_root(tmp_path):
    dom = {"css_tokens": {
        "color": [{"name": "--brand", "value": "#f60"}],
        "spacing": [{"name": "--s", "value": "8px"}],
        "font": [], "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")
    tokens_css = (result.output_dir / "tokens.css").read_text()
    assert ":root {" in tokens_css
    assert "--brand: #f60;" in tokens_css
    assert "--s: 8px;" in tokens_css
    assert "https://x.com" in tokens_css  # header comment


def test_tokens_json_has_figma_shape(tmp_path):
    dom = {"css_tokens": {
        "color": [{"name": "--brand", "value": "#f60"}],
        "spacing": [{"name": "--s", "value": "8px"}],
        "font": [], "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")
    data = json.loads((result.output_dir / "tokens.json").read_text())
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["strategy"] == "direct"
    assert data["source_url"] == "https://x.com"
    assert len(data["tokens"]) == 2
    for t in data["tokens"]:
        assert set(t.keys()) == {"name", "value", "type"}
        assert t["type"] in {"color", "dimension", "string"}


def test_tailwind_config_has_extend_block(tmp_path):
    dom = {"css_tokens": {
        "color": [{"name": "--brand", "value": "#f60"}],
        "spacing": [{"name": "--space-sm", "value": "8px"}],
        "font": [{"name": "--font-sans", "value": "Inter"}],
        "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")
    tw = (result.output_dir / "tailwind.config.js").read_text()
    assert "module.exports" in tw
    assert "theme:" in tw
    assert "extend:" in tw
    assert "colors:" in tw
    assert "spacing:" in tw
    assert "var(--brand)" in tw


def test_tailwind_skipped_when_empty(tmp_path):
    dom = {
        "css_tokens": {"color": [], "spacing": [], "font": [], "radius": [], "other": []},
        "colors": {"text": [], "background": []},
        "fonts": {"families": [], "sizes": []},
        "spacing_values": [],
    }
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")
    assert not (result.output_dir / "tailwind.config.js").exists()


def test_readme_documents_source_and_counts(tmp_path):
    dom = {"css_tokens": {
        "color": [{"name": "--c", "value": "#000"}, {"name": "--d", "value": "#fff"}],
        "spacing": [{"name": "--s", "value": "8px"}],
        "font": [], "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")
    readme = (result.output_dir / "README.md").read_text()
    assert "https://x.com" in readme
    assert "direct" in readme
    assert "| Colours | 2 |" in readme
    assert "| Spacing | 1 |" in readme
    assert "Total" in readme


def test_write_result_json_serialisable(tmp_path):
    dom = {"css_tokens": {
        "color": [{"name": "--c", "value": "#000"}],
        "spacing": [], "font": [], "radius": [], "other": [],
    }}
    system = extract_system(dom, "https://x.com")
    result = write_system_to_dir(system, tmp_path / "out")
    data = json.loads(result.to_json())
    assert "output_dir" in data
    assert "files_written" in data
    assert data["strategy"] == "direct"
    assert data["total"] == 1


def test_counts_by_category():
    system = extract_system(
        {"css_tokens": {
            "color": [{"name": "--a", "value": "#000"}, {"name": "--b", "value": "#111"}],
            "spacing": [{"name": "--s", "value": "8px"}],
            "font": [{"name": "--f", "value": "x"}],
            "radius": [], "other": [],
        }},
        "https://x.com",
    )
    counts = system.counts_by_category()
    assert counts == {"colours": 2, "typography": 1, "spacing": 1, "radius": 0, "other": 0}
    assert system.total_count == 4


# ── Token dataclass ──


def test_token_css_line_format():
    t = Token(name="--brand", value="#ff0000", type="color")
    assert t.css_line() == "  --brand: #ff0000;"


def test_token_figma_dict_shape():
    t = Token(name="--brand", value="#ff0000", type="color")
    assert t.to_figma_dict() == {"name": "--brand", "value": "#ff0000", "type": "color"}
