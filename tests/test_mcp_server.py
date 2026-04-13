"""Smoke tests for the MCP server surface.

Verifies that tools and resources register correctly and that the knowledge
library is exposed. Live tools (critique, wcag, fix, etc.) hit Playwright and
the network, so they're not invoked here — only their registration is checked.
"""

import asyncio


from src.mcp_server import mcp, _iter_knowledge_entries, KNOWLEDGE_ROOT


EXPECTED_TOOLS = {"critique", "wcag", "components", "handoff", "fix", "compare", "diff"}


def _run(coro):
    return asyncio.run(coro)


def test_all_expected_tools_registered():
    tools = _run(mcp.list_tools())
    names = {t.name for t in tools}
    assert EXPECTED_TOOLS.issubset(names), (
        f"missing tools: {EXPECTED_TOOLS - names}"
    )


def test_every_tool_has_a_description():
    tools = _run(mcp.list_tools())
    for t in tools:
        assert t.description, f"tool {t.name} has no description"
        assert len(t.description) > 20, f"tool {t.name} description too short"


def test_every_tool_requires_url():
    tools = _run(mcp.list_tools())
    for t in tools:
        schema = t.inputSchema or {}
        properties = schema.get("properties", {})
        assert "url" in properties, f"tool {t.name} missing url parameter"


def test_knowledge_resource_template_registered():
    templates = _run(mcp.list_resource_templates())
    template_uris = {t.uriTemplate for t in templates}
    assert "design-intel://knowledge/{category}/{slug}" in template_uris


def test_knowledge_index_resource_registered():
    resources = _run(mcp.list_resources())
    uris = {str(r.uri) for r in resources}
    assert "design-intel://knowledge/index" in uris


def test_knowledge_index_lists_all_entries():
    contents = _run(mcp.read_resource("design-intel://knowledge/index"))
    body = list(contents)[0].content
    entries_on_disk = list(_iter_knowledge_entries())
    assert len(entries_on_disk) >= 30, (
        "expected at least 30 knowledge entries on disk"
    )
    for category, slug, _ in entries_on_disk:
        uri = f"design-intel://knowledge/{category}/{slug}"
        assert uri in body, f"index missing {uri}"


def test_read_specific_knowledge_entry():
    # Pick the first entry on disk and verify we can read it.
    category, slug, path = next(iter(_iter_knowledge_entries()))
    contents = _run(
        mcp.read_resource(f"design-intel://knowledge/{category}/{slug}")
    )
    body = list(contents)[0].content
    assert body.strip(), "entry body is empty"
    assert body == path.read_text()


def test_knowledge_resource_rejects_missing_entry():
    contents = _run(
        mcp.read_resource("design-intel://knowledge/accessibility/does-not-exist")
    )
    body = list(contents)[0].content
    assert "not found" in body.lower()


def test_knowledge_resource_rejects_path_traversal():
    # A slug containing ".." would escape the knowledge root if not guarded.
    # The URI template won't route traversal-style slugs straightforwardly,
    # so assert that crafted inputs to the underlying function are rejected.
    from src.mcp_server import knowledge_entry
    # A legit-looking but non-existent entry returns the not-found message.
    result = knowledge_entry("accessibility", "../../etc/passwd")
    assert "not found" in result.lower() or "invalid" in result.lower()


def test_pending_knowledge_folder_excluded():
    # The pending/ folder holds draft entries and should not leak into the index.
    for category, _slug, _ in _iter_knowledge_entries():
        assert category != "pending", "pending entries should not be indexed"


def test_compare_tool_schema_requires_url_and_competitor():
    tools = _run(mcp.list_tools())
    compare_tool = next((t for t in tools if t.name == "compare"), None)
    assert compare_tool is not None
    props = (compare_tool.inputSchema or {}).get("properties", {})
    assert "url" in props
    assert "competitor" in props


def test_fix_tool_description_mentions_wcag():
    tools = _run(mcp.list_tools())
    fix_tool = next((t for t in tools if t.name == "fix"), None)
    assert fix_tool is not None
    assert "wcag" in fix_tool.description.lower()


def test_wcag_tool_description_mentions_deterministic():
    tools = _run(mcp.list_tools())
    wcag_tool = next((t for t in tools if t.name == "wcag"), None)
    assert wcag_tool is not None
    assert "deterministic" in wcag_tool.description.lower()


def test_knowledge_root_exists():
    assert KNOWLEDGE_ROOT.exists(), "knowledge/ directory missing"
    assert KNOWLEDGE_ROOT.is_dir()
