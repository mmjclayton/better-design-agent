"""
Custom design-rule engine.

Reads a project-local `.design-intel/rules.yaml` file and validates the
live site's DOM against it. Five rule types cover most brand-enforcement
needs: allowed fonts, allowed colours (by context), min font size,
required tokens, forbidden tokens.

Deterministic — no LLM. Missing or malformed rules files surface as
technical errors, not silent passes.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path

import yaml


SCHEMA_VERSION = 1

EXIT_PASS = 0
EXIT_VIOLATIONS = 1
EXIT_TECHNICAL_ERROR = 2

DEFAULT_RULES_PATH = Path(".design-intel/rules.yaml")

VALID_RULE_KEYS = {
    "version",
    "allowed_fonts",
    "allowed_colours",
    "min_font_size",
    "required_tokens",
    "forbidden_tokens",
}


# ── Loading + parsing ──


@dataclass
class BrandRules:
    """Typed view over the rules YAML file."""
    allowed_fonts: list[str] = field(default_factory=list)
    allowed_colours_text: list[str] = field(default_factory=list)
    allowed_colours_background: list[str] = field(default_factory=list)
    min_font_size: int | None = None
    required_tokens: list[str] = field(default_factory=list)
    forbidden_tokens: list[str] = field(default_factory=list)

    @property
    def is_empty(self) -> bool:
        return (
            not self.allowed_fonts
            and not self.allowed_colours_text
            and not self.allowed_colours_background
            and self.min_font_size is None
            and not self.required_tokens
            and not self.forbidden_tokens
        )


class RulesLoadError(Exception):
    """Raised when the rules file can't be loaded or parsed."""


def load_rules(path: Path) -> BrandRules:
    """Load a rules YAML file and return a typed BrandRules."""
    if not path.exists():
        raise RulesLoadError(
            f"Rules file not found at {path}. "
            f"Create one — see examples/brand-rules-example.yaml."
        )
    try:
        raw = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise RulesLoadError(f"Rules file is malformed YAML: {exc}") from exc

    if raw is None:
        return BrandRules()
    if not isinstance(raw, dict):
        raise RulesLoadError(
            f"Rules file must be a YAML mapping; got {type(raw).__name__}."
        )

    unknown = set(raw.keys()) - VALID_RULE_KEYS
    if unknown:
        raise RulesLoadError(
            f"Unknown rule key(s): {sorted(unknown)}. "
            f"Valid keys: {sorted(VALID_RULE_KEYS)}"
        )

    colours = raw.get("allowed_colours") or {}
    if colours and not isinstance(colours, dict):
        raise RulesLoadError(
            "allowed_colours must be a mapping with 'text' and/or 'background' lists."
        )

    return BrandRules(
        allowed_fonts=list(raw.get("allowed_fonts") or []),
        allowed_colours_text=[_normalise_hex(c) for c in (colours.get("text") or [])],
        allowed_colours_background=[
            _normalise_hex(c) for c in (colours.get("background") or [])
        ],
        min_font_size=raw.get("min_font_size"),
        required_tokens=list(raw.get("required_tokens") or []),
        forbidden_tokens=list(raw.get("forbidden_tokens") or []),
    )


def _normalise_hex(value: str) -> str:
    """Lowercase + strip #. Expand 3-char shorthand to 6 chars."""
    if not isinstance(value, str):
        return ""
    v = value.strip().lower().lstrip("#")
    if len(v) == 3:
        v = "".join(c * 2 for c in v)
    return v


# ── Rule evaluation ──


@dataclass
class RuleResult:
    name: str
    passed: bool
    detail: str
    violations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BrandComplianceReport:
    schema_version: int
    url: str
    rules_path: str
    results: list[RuleResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors and all(r.passed for r in self.results)

    @property
    def violation_count(self) -> int:
        return sum(len(r.violations) for r in self.results if not r.passed)

    @property
    def exit_code(self) -> int:
        if self.errors:
            return EXIT_TECHNICAL_ERROR
        if any(not r.passed for r in self.results):
            return EXIT_VIOLATIONS
        return EXIT_PASS

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "url": self.url,
            "rules_path": self.rules_path,
            "passed": self.passed,
            "violation_count": self.violation_count,
            "exit_code": self.exit_code,
            "results": [r.to_dict() for r in self.results],
            "errors": self.errors,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    def to_markdown(self) -> str:
        lines = [
            "# Brand Compliance Report",
            "",
            f"**URL:** {self.url}",
            f"**Rules:** {self.rules_path}",
            f"**Status:** {'PASS' if self.passed else 'FAIL'}  "
            f"(**{self.violation_count}** total violation(s))",
            "",
        ]
        if self.errors:
            lines.append("## Errors")
            for e in self.errors:
                lines.append(f"- {e}")
            lines.append("")

        if self.results:
            lines.append("## Rule Results")
            lines.append("")
            for r in self.results:
                status = "PASS" if r.passed else "FAIL"
                lines.append(f"### [{status}] {r.name}")
                lines.append("")
                lines.append(r.detail)
                if r.violations:
                    lines.append("")
                    for v in r.violations[:20]:
                        lines.append(f"- {v}")
                    if len(r.violations) > 20:
                        lines.append(f"- … +{len(r.violations) - 20} more")
                lines.append("")
        else:
            lines.append("_No rules configured — add rules to `.design-intel/rules.yaml`._")
            lines.append("")

        lines.append(f"**Exit code:** {self.exit_code}")
        return "\n".join(lines)


# ── Individual rule checks ──


def _first_family(family_stack: str) -> str:
    """Extract the first family from a CSS font-family stack."""
    # "Inter, sans-serif" → "Inter"
    first = family_stack.split(",")[0].strip().strip('"').strip("'")
    return first.lower()


def check_allowed_fonts(rules: BrandRules, dom_data: dict) -> RuleResult:
    if not rules.allowed_fonts:
        return RuleResult(
            name="allowed_fonts", passed=True, detail="Rule not configured.",
        )
    allowed = {f.lower() for f in rules.allowed_fonts}
    families = (dom_data.get("fonts", {}) or {}).get("families", []) or []
    violations: list[str] = []
    checked = 0
    for entry in families:
        raw = entry.get("family") or entry.get("value") or ""
        if not raw:
            continue
        checked += 1
        first = _first_family(str(raw))
        # Accept if any allowed font name appears in the first-family string.
        if not any(a.lower() in first for a in allowed):
            violations.append(f"'{raw}' (first family: '{first}')")
    if violations:
        return RuleResult(
            name="allowed_fonts", passed=False,
            detail=f"{len(violations)} font(s) outside the allowed list ({sorted(allowed)}).",
            violations=violations,
        )
    return RuleResult(
        name="allowed_fonts", passed=True,
        detail=f"All {checked} font families match the allowed list.",
    )


def check_allowed_colours(rules: BrandRules, dom_data: dict) -> RuleResult:
    if not rules.allowed_colours_text and not rules.allowed_colours_background:
        return RuleResult(
            name="allowed_colours", passed=True, detail="Rule not configured.",
        )
    colours = dom_data.get("colors", {}) or {}
    violations: list[str] = []

    def _check_bucket(bucket: list[dict], allowed: list[str], label: str):
        if not allowed:
            return
        allowed_set = set(allowed)
        for entry in bucket:
            raw = entry.get("color") or entry.get("value") or ""
            if not raw:
                continue
            norm = _normalise_hex(str(raw))
            if norm and norm not in allowed_set:
                violations.append(f"{label}: '{raw}' not in palette")

    _check_bucket(colours.get("text", []) or [], rules.allowed_colours_text, "text")
    _check_bucket(
        colours.get("background", []) or [],
        rules.allowed_colours_background, "background",
    )

    if violations:
        return RuleResult(
            name="allowed_colours", passed=False,
            detail=f"{len(violations)} colour(s) outside the palette.",
            violations=violations,
        )
    return RuleResult(
        name="allowed_colours", passed=True,
        detail="All colours match the brand palette.",
    )


def check_min_font_size(rules: BrandRules, dom_data: dict) -> RuleResult:
    if rules.min_font_size is None:
        return RuleResult(
            name="min_font_size", passed=True, detail="Rule not configured.",
        )
    min_px = rules.min_font_size
    sizes = (dom_data.get("fonts", {}) or {}).get("sizes", []) or []
    violations: list[str] = []
    for entry in sizes:
        raw = entry.get("size") or entry.get("value") or ""
        if not raw:
            continue
        px = _parse_px(str(raw))
        if px is not None and px < min_px:
            violations.append(f"'{raw}' below {min_px}px minimum")
    if violations:
        return RuleResult(
            name="min_font_size", passed=False,
            detail=f"{len(violations)} font size(s) below {min_px}px.",
            violations=violations,
        )
    return RuleResult(
        name="min_font_size", passed=True,
        detail=f"All font sizes ≥ {min_px}px.",
    )


def check_required_tokens(rules: BrandRules, dom_data: dict) -> RuleResult:
    if not rules.required_tokens:
        return RuleResult(
            name="required_tokens", passed=True, detail="Rule not configured.",
        )
    present = _all_token_names(dom_data)
    missing = [t for t in rules.required_tokens if t not in present]
    if missing:
        return RuleResult(
            name="required_tokens", passed=False,
            detail=f"{len(missing)} required token(s) missing.",
            violations=[f"'{t}' not defined" for t in missing],
        )
    return RuleResult(
        name="required_tokens", passed=True,
        detail=f"All {len(rules.required_tokens)} required tokens present.",
    )


def check_forbidden_tokens(rules: BrandRules, dom_data: dict) -> RuleResult:
    if not rules.forbidden_tokens:
        return RuleResult(
            name="forbidden_tokens", passed=True, detail="Rule not configured.",
        )
    present = _all_token_names(dom_data)
    found = [t for t in rules.forbidden_tokens if t in present]
    if found:
        return RuleResult(
            name="forbidden_tokens", passed=False,
            detail=f"{len(found)} forbidden token(s) found.",
            violations=[f"'{t}' still defined" for t in found],
        )
    return RuleResult(
        name="forbidden_tokens", passed=True,
        detail="No forbidden tokens present.",
    )


def _all_token_names(dom_data: dict) -> set[str]:
    tokens = dom_data.get("css_tokens", {}) or {}
    names: set[str] = set()
    for bucket in tokens.values():
        for entry in bucket or []:
            name = entry.get("name")
            if name:
                names.add(name)
    return names


def _parse_px(value: str) -> float | None:
    match = re.match(r"^([\d.]+)\s*px$", value.strip())
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            return None
    return None


# ── Main entry ──


def evaluate_rules(
    rules: BrandRules,
    dom_data: dict,
    url: str,
    rules_path: str,
) -> BrandComplianceReport:
    """Run every configured rule check and assemble the report."""
    results = [
        check_allowed_fonts(rules, dom_data),
        check_allowed_colours(rules, dom_data),
        check_min_font_size(rules, dom_data),
        check_required_tokens(rules, dom_data),
        check_forbidden_tokens(rules, dom_data),
    ]
    return BrandComplianceReport(
        schema_version=SCHEMA_VERSION,
        url=url,
        rules_path=rules_path,
        results=results,
    )
