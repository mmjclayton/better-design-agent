"""
Axe-core integration via Playwright.

Injects axe-core into the page and runs a full accessibility audit.
Returns structured results that integrate with our WCAG reporting.
"""

from dataclasses import dataclass, field

# axe-core CDN URL — pinned version for reproducibility
AXE_CDN_URL = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"

AXE_RUN_SCRIPT = """
async () => {
    // Wait for axe to be available
    if (typeof axe === 'undefined') return { error: 'axe-core not loaded' };

    try {
        const results = await axe.run(document, {
            runOnly: {
                type: 'tag',
                values: ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa', 'best-practice']
            },
            resultTypes: ['violations', 'passes', 'incomplete']
        });

        return {
            violations: results.violations.map(v => ({
                id: v.id,
                impact: v.impact,
                description: v.description,
                help: v.help,
                helpUrl: v.helpUrl,
                tags: v.tags,
                nodes: v.nodes.slice(0, 10).map(n => ({
                    html: n.html?.substring(0, 200),
                    target: n.target,
                    failureSummary: n.failureSummary,
                })),
            })),
            passes: results.passes.map(p => ({
                id: p.id,
                description: p.description,
                nodes_count: p.nodes.length,
            })),
            incomplete: results.incomplete.map(i => ({
                id: i.id,
                impact: i.impact,
                description: i.description,
                nodes_count: i.nodes.length,
            })),
            url: results.url,
            timestamp: results.timestamp,
        };
    } catch (e) {
        return { error: e.message };
    }
}
"""


@dataclass
class AxeResult:
    violations: list[dict] = field(default_factory=list)
    passes: list[dict] = field(default_factory=list)
    incomplete: list[dict] = field(default_factory=list)
    url: str = ""
    error: str = ""

    @property
    def violation_count(self) -> int:
        return len(self.violations)

    @property
    def pass_count(self) -> int:
        return len(self.passes)

    @property
    def critical_count(self) -> int:
        return sum(1 for v in self.violations if v.get("impact") == "critical")

    @property
    def serious_count(self) -> int:
        return sum(1 for v in self.violations if v.get("impact") == "serious")

    def to_markdown(self) -> str:
        lines = [
            "## Axe-core Accessibility Audit\n",
            f"**{self.violation_count} violations** ({self.critical_count} critical, "
            f"{self.serious_count} serious) | "
            f"**{self.pass_count} rules passing** | "
            f"**{len(self.incomplete)} needs review**\n",
        ]

        if self.error:
            lines.append(f"**Error:** {self.error}\n")
            return "\n".join(lines)

        # Violations by impact
        if self.violations:
            # Group by impact
            for impact in ["critical", "serious", "moderate", "minor"]:
                impact_violations = [v for v in self.violations if v.get("impact") == impact]
                if not impact_violations:
                    continue

                impact_label = {
                    "critical": "Critical (must fix)",
                    "serious": "Serious (should fix)",
                    "moderate": "Moderate",
                    "minor": "Minor",
                }.get(impact, impact)

                lines.append(f"\n### {impact_label} ({len(impact_violations)})\n")

                for v in impact_violations:
                    rule_id = v.get("id", "?")
                    description = v.get("description", "")
                    help_text = v.get("help", "")
                    help_url = v.get("helpUrl", "")
                    nodes = v.get("nodes", [])

                    lines.append(f"**{rule_id}**: {help_text}")
                    lines.append(f"  {description}")

                    if nodes:
                        lines.append(f"  Affected elements ({len(nodes)}):")
                        for n in nodes[:5]:
                            target = n.get("target", ["?"])
                            target_str = " > ".join(target) if isinstance(target, list) else str(target)
                            html = n.get("html", "")[:100]
                            lines.append(f"  - `{target_str}`")
                            if html:
                                lines.append(f"    `{html}`")
                    lines.append("")

        # Passes summary
        if self.passes:
            lines.append(f"\n### Passing Rules ({self.pass_count})\n")
            # Group into a compact list
            pass_names = [p.get("id", "?") for p in self.passes]
            # Show in rows of 4
            for i in range(0, len(pass_names), 4):
                chunk = pass_names[i:i+4]
                lines.append("  " + ", ".join(f"`{p}`" for p in chunk))
            lines.append("")

        # Incomplete
        if self.incomplete:
            lines.append(f"\n### Needs Manual Review ({len(self.incomplete)})\n")
            for i in self.incomplete:
                lines.append(f"- **{i.get('id', '?')}** ({i.get('impact', '?')}): {i.get('description', '')}")
            lines.append("")

        return "\n".join(lines)


async def run_axe_on_page(page) -> AxeResult:
    """Inject axe-core and run accessibility audit on a Playwright page."""

    # Inject axe-core
    try:
        await page.add_script_tag(url=AXE_CDN_URL)
        # Wait for axe to be available
        await page.wait_for_function("typeof axe !== 'undefined'", timeout=10000)
    except Exception as e:
        return AxeResult(error=f"Failed to load axe-core: {str(e)[:100]}")

    # Run axe
    try:
        raw = await page.evaluate(AXE_RUN_SCRIPT)
    except Exception as e:
        return AxeResult(error=f"Failed to run axe: {str(e)[:100]}")

    if isinstance(raw, dict) and raw.get("error"):
        return AxeResult(error=raw["error"])

    return AxeResult(
        violations=raw.get("violations", []),
        passes=raw.get("passes", []),
        incomplete=raw.get("incomplete", []),
        url=raw.get("url", ""),
    )
