import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright


# Real Chrome user agent to avoid bot detection
CHROME_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)

# Stealth mode flag — set by CLI
_stealth_mode = False


def set_stealth_mode(enabled: bool):
    global _stealth_mode
    _stealth_mode = enabled


async def _launch_browser(p, headed: bool = False):
    """Launch browser with optional stealth patches."""
    if _stealth_mode:
        browser = await p.chromium.launch(
            headless=not headed,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ],
        )
    else:
        browser = await p.chromium.launch(headless=not headed)
    return browser


async def _new_stealth_page(browser, viewport_width: int, viewport_height: int):
    """Create a page with stealth patches applied."""
    context = await browser.new_context(
        viewport={"width": viewport_width, "height": viewport_height},
        user_agent=CHROME_USER_AGENT if _stealth_mode else None,
        locale="en-AU",
        timezone_id="Australia/Sydney",
    )

    page = await context.new_page()

    if _stealth_mode:
        # Patch navigator.webdriver to return false
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-AU', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });

            // Override permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) =>
                parameters.name === 'notifications'
                    ? Promise.resolve({ state: Notification.permission })
                    : originalQuery(parameters);

            // Chrome runtime
            window.chrome = { runtime: {} };
        """)

    return page

# JavaScript to extract computed styles, design metrics, and HTML structure
DOM_EXTRACTION_SCRIPT = """
() => {
    const results = {
        colors: {},
        fonts: {},
        contrast_pairs: [],
        interactive_elements: [],
        layout: {},
        css_tokens: {},
        html_structure: {},
        focus_audit: [],
        non_text_contrast: [],
        spacing_values: [],
    };

    const allElements = document.querySelectorAll('body *');
    const colorCounts = {};
    const bgColorCounts = {};
    const fontSizes = {};
    const fontFamilies = {};
    const spacingValues = {};

    function parseRgba(rgb) {
        if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') return null;
        const match = rgb.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)(?:,\\s*([\\d.]+))?/);
        if (!match) return null;
        return {
            r: parseInt(match[1]),
            g: parseInt(match[2]),
            b: parseInt(match[3]),
            a: match[4] !== undefined ? parseFloat(match[4]) : 1,
        };
    }

    function compositeOver(fg, bg) {
        // Alpha composite fg colour over bg colour
        const a = fg.a;
        return {
            r: Math.round(fg.r * a + bg.r * (1 - a)),
            g: Math.round(fg.g * a + bg.g * (1 - a)),
            b: Math.round(fg.b * a + bg.b * (1 - a)),
            a: 1,
        };
    }

    function rgbaToHex(rgba) {
        if (!rgba) return null;
        return '#' + [rgba.r, rgba.g, rgba.b]
            .map(x => Math.min(255, Math.max(0, x)).toString(16).padStart(2, '0'))
            .join('');
    }

    function rgbToHex(rgb) {
        const parsed = parseRgba(rgb);
        if (!parsed) return null;
        // If fully transparent, return null
        if (parsed.a === 0) return null;
        // If semi-transparent, still convert (compositing handled in getEffectiveBg)
        return rgbaToHex(parsed);
    }

    function getLuminance(hex) {
        if (!hex || !hex.startsWith('#')) return null;
        const rgb = hex.replace('#', '').match(/.{2}/g)
            .map(x => {
                const c = parseInt(x, 16) / 255;
                return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
            });
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2];
    }

    function getContrastRatio(hex1, hex2) {
        const l1 = getLuminance(hex1);
        const l2 = getLuminance(hex2);
        if (l1 === null || l2 === null) return null;
        const lighter = Math.max(l1, l2);
        const darker = Math.min(l1, l2);
        return Math.round(((lighter + 0.05) / (darker + 0.05)) * 100) / 100;
    }

    function getEffectiveBg(el) {
        // Walk up the DOM, compositing semi-transparent backgrounds
        // to get the actual rendered background colour
        const layers = [];
        let current = el;
        while (current && current !== document.documentElement) {
            const bg = getComputedStyle(current).backgroundColor;
            const parsed = parseRgba(bg);
            if (parsed && parsed.a > 0) {
                layers.unshift(parsed); // Add to front (bottom-up order)
                if (parsed.a >= 1) break; // Fully opaque, stop walking
            }
            current = current.parentElement;
        }

        // Start with white fallback, composite each layer on top
        let result = { r: 255, g: 255, b: 255, a: 1 };
        for (const layer of layers) {
            result = compositeOver(layer, result);
        }
        return rgbaToHex(result);
    }

    // ── CSS Custom Properties (Design Tokens) ──
    // Strategy 1: Read from stylesheet rules (works for plain CSS)
    // Strategy 2: Read computed styles from :root (works for bundlers like Vite/React)
    // Strategy 3: Read inline style attributes on :root
    const tokenCategories = { color: [], spacing: [], radius: [], font: [], other: [] };
    const seenTokens = new Set();

    function categorizeToken(name, value) {
        if (seenTokens.has(name)) return;
        seenTokens.add(name);
        const entry = { name, value };

        if (/color|bg|text|accent|surface|border|success|warning|danger|primary|secondary|muted/.test(name)) {
            tokenCategories.color.push(entry);
        } else if (/space|gap|padding|margin/.test(name)) {
            tokenCategories.spacing.push(entry);
        } else if (/radius|round/.test(name)) {
            tokenCategories.radius.push(entry);
        } else if (/font|type|size|weight|line-height|letter/.test(name)) {
            tokenCategories.font.push(entry);
        } else {
            tokenCategories.other.push(entry);
        }
    }

    // Strategy 1: Iterate stylesheet rules
    for (const sheet of document.styleSheets) {
        try {
            for (const rule of sheet.cssRules) {
                const sel = rule.selectorText || '';
                if (sel.includes(':root') || sel.includes(':host') || sel === 'html') {
                    for (const prop of rule.style) {
                        if (prop.startsWith('--')) {
                            const value = rule.style.getPropertyValue(prop).trim();
                            categorizeToken(prop, value);
                        }
                    }
                }
            }
        } catch (e) { /* cross-origin stylesheet, skip */ }
    }

    // Strategy 2: Read computed custom properties from all <style> tags
    // (catches Vite/React injected styles that may not be in document.styleSheets)
    for (const styleEl of document.querySelectorAll('style')) {
        const text = styleEl.textContent || '';
        const matches = text.matchAll(/--([a-zA-Z0-9-]+)\s*:\s*([^;]+)/g);
        for (const match of matches) {
            const name = '--' + match[1];
            const value = match[2].trim();
            categorizeToken(name, value);
        }
    }

    // Strategy 3: Get computed values for any tokens found, plus probe common token names
    const rootStyles = getComputedStyle(document.documentElement);
    const commonTokenPrefixes = [
        'color', 'bg', 'text', 'accent', 'surface', 'border', 'primary', 'secondary',
        'space', 'gap', 'padding', 'margin',
        'radius', 'font', 'type', 'size', 'weight',
        'shadow', 'transition', 'duration', 'ease',
        'success', 'warning', 'danger', 'error', 'info',
        'muted', 'disabled', 'hover', 'focus', 'active',
    ];
    // Check if we found any tokens - if not, try probing computed styles
    if (seenTokens.size === 0) {
        // Fallback: scan all <style> content for custom property declarations
        const allStyles = document.querySelectorAll('style, link[rel="stylesheet"]');
        // Try reading properties that are commonly defined
        for (const prefix of commonTokenPrefixes) {
            for (const suffix of ['', '-primary', '-secondary', '-base', '-sm', '-md', '-lg', '-xl', '-1', '-2', '-3', '-4', '-5', '-6', '-8']) {
                const prop = '--' + prefix + suffix;
                const val = rootStyles.getPropertyValue(prop).trim();
                if (val) {
                    categorizeToken(prop, val);
                }
            }
        }
    }

    results.css_tokens = tokenCategories;

    // ── HTML Structure Audit ──
    const htmlAudit = {
        has_lang: !!document.documentElement.lang,
        lang_value: document.documentElement.lang || null,
        title: document.title || null,
        landmarks: {
            main: document.querySelectorAll('main, [role="main"]').length,
            nav: document.querySelectorAll('nav, [role="navigation"]').length,
            aside: document.querySelectorAll('aside, [role="complementary"]').length,
            header: document.querySelectorAll('header, [role="banner"]').length,
            footer: document.querySelectorAll('footer, [role="contentinfo"]').length,
        },
        headings: [],
        skip_link: false,
        forms: { inputs_without_labels: [], selects_without_labels: [] },
        aria_usage: { roles: [], labels: 0, described_by: 0, live_regions: 0 },
        images_without_alt: 0,
    };

    // Headings
    for (const level of [1, 2, 3, 4, 5, 6]) {
        const headings = document.querySelectorAll('h' + level);
        for (const h of headings) {
            htmlAudit.headings.push({
                level: level,
                text: h.textContent.trim().substring(0, 80),
            });
        }
    }

    // Skip link detection
    const firstLink = document.querySelector('a[href^="#"]');
    if (firstLink) {
        const text = firstLink.textContent.toLowerCase();
        htmlAudit.skip_link = /skip|jump|main/.test(text);
    }

    // Form labels
    for (const input of document.querySelectorAll('input, textarea')) {
        const hasLabel = input.labels?.length > 0
            || input.getAttribute('aria-label')
            || input.getAttribute('aria-labelledby')
            || input.getAttribute('title');
        if (!hasLabel && input.type !== 'hidden') {
            htmlAudit.forms.inputs_without_labels.push({
                type: input.type || 'text',
                placeholder: input.placeholder || null,
                selector: input.tagName.toLowerCase()
                    + (input.className ? '.' + input.className.toString().split(' ')[0] : ''),
            });
        }
    }
    for (const select of document.querySelectorAll('select')) {
        const hasLabel = select.labels?.length > 0
            || select.getAttribute('aria-label')
            || select.getAttribute('aria-labelledby');
        if (!hasLabel) {
            htmlAudit.forms.selects_without_labels.push({
                selector: select.tagName.toLowerCase()
                    + (select.className ? '.' + select.className.toString().split(' ')[0] : ''),
                first_option: select.options[0]?.textContent?.trim() || null,
            });
        }
    }

    // ARIA usage
    const rolesUsed = new Set();
    for (const el of document.querySelectorAll('[role]')) {
        rolesUsed.add(el.getAttribute('role'));
    }
    htmlAudit.aria_usage.roles = [...rolesUsed];
    htmlAudit.aria_usage.labels = document.querySelectorAll('[aria-label]').length;
    htmlAudit.aria_usage.described_by = document.querySelectorAll('[aria-describedby]').length;
    htmlAudit.aria_usage.live_regions = document.querySelectorAll('[aria-live]').length;

    // Images without alt
    htmlAudit.images_without_alt = document.querySelectorAll('img:not([alt])').length;

    // Check for global :focus-visible rules in stylesheets
    htmlAudit.has_global_focus_visible = false;
    htmlAudit.focus_visible_rules = [];
    for (const sheet of document.styleSheets) {
        try {
            for (const rule of sheet.cssRules) {
                const sel = rule.selectorText || '';
                if (sel.includes(':focus-visible') || sel.includes(':focus')) {
                    htmlAudit.has_global_focus_visible = true;
                    // Check if it's a broad selector (global coverage)
                    if (sel.match(/^[*a-z,\\s]+:focus/) || sel.includes('*:focus')) {
                        htmlAudit.focus_visible_rules.push({
                            selector: sel,
                            properties: rule.cssText.substring(0, 200),
                        });
                    }
                }
            }
        } catch (e) { /* cross-origin */ }
    }
    // Also check <style> tags for bundled styles
    if (!htmlAudit.has_global_focus_visible) {
        for (const styleEl of document.querySelectorAll('style')) {
            const text = styleEl.textContent || '';
            if (text.includes(':focus-visible') || text.includes(':focus')) {
                htmlAudit.has_global_focus_visible = true;
                const matches = text.match(/[^{]*:focus-visible[^{]*\\{[^}]*\\}/g) || [];
                for (const m of matches.slice(0, 5)) {
                    htmlAudit.focus_visible_rules.push({
                        selector: m.split('{')[0].trim(),
                        properties: m.substring(0, 200),
                    });
                }
            }
        }
    }

    results.html_structure = htmlAudit;

    // ── Element Analysis ──
    const contrastPairs = [];
    const seen = new Set();
    const interactiveElements = [];

    for (const el of allElements) {
        const style = getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') continue;

        const color = rgbToHex(style.color);
        const bgColor = rgbToHex(style.backgroundColor);
        if (color) colorCounts[color] = (colorCounts[color] || 0) + 1;
        if (bgColor) bgColorCounts[bgColor] = (bgColorCounts[bgColor] || 0) + 1;

        // Fonts — round sub-pixel values to filter browser rendering artifacts
        const rawFontSize = style.fontSize;
        const fontSizeNum = parseFloat(rawFontSize);
        const fontSize = fontSizeNum ? (Math.round(fontSizeNum) + 'px') : rawFontSize;
        const fontFamily = style.fontFamily.split(',')[0].trim().replace(/['"]/g, '');
        if (fontSize) fontSizes[fontSize] = (fontSizes[fontSize] || 0) + 1;
        if (fontFamily) fontFamilies[fontFamily] = (fontFamilies[fontFamily] || 0) + 1;

        // Spacing values (padding and margin)
        for (const prop of ['paddingTop', 'paddingBottom', 'paddingLeft', 'paddingRight',
                            'marginTop', 'marginBottom', 'gap']) {
            const val = style[prop];
            if (val && val !== '0px' && val !== 'normal' && val !== 'auto') {
                spacingValues[val] = (spacingValues[val] || 0) + 1;
            }
        }

        // Contrast pairs
        const text = el.textContent?.trim();
        if (text && text.length > 0 && text.length < 200 && color) {
            const effectiveBg = getEffectiveBg(el);
            const ratio = getContrastRatio(color, effectiveBg);
            const tag = el.tagName.toLowerCase();
            const key = `${color}|${effectiveBg}`;
            if (ratio && !seen.has(key)) {
                seen.add(key);
                const sizeNum = parseFloat(fontSize);
                const weight = parseInt(style.fontWeight) || 400;
                const isLarge = sizeNum >= 24 || (sizeNum >= 18.66 && weight >= 700);
                const required = isLarge ? 3 : 4.5;
                const passes = ratio >= required;
                contrastPairs.push({
                    text_color: color,
                    bg_color: effectiveBg,
                    ratio: ratio,
                    passes_aa: passes,
                    required: required,
                    font_size: fontSize,
                    font_weight: weight,
                    sample_text: text.substring(0, 60),
                    element: tag + (el.className ? '.' + el.className.toString().split(' ')[0] : ''),
                });
            }
        }

        // Interactive elements
        const isInteractive = ['A', 'BUTTON', 'INPUT', 'SELECT', 'TEXTAREA'].includes(el.tagName)
            || el.getAttribute('role') === 'button'
            || el.getAttribute('tabindex') !== null;

        if (isInteractive) {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0) {
                const selector = el.tagName.toLowerCase()
                    + (el.className ? '.' + el.className.toString().split(' ')[0] : '');

                interactiveElements.push({
                    element: selector,
                    text: (el.textContent || el.getAttribute('placeholder') || '').trim().substring(0, 40),
                    width: Math.round(rect.width),
                    height: Math.round(rect.height),
                    meets_touch_target: rect.width >= 44 && rect.height >= 44,
                    has_aria_label: !!el.getAttribute('aria-label'),
                    has_visible_label: !!(el.labels?.length || el.textContent?.trim()),
                });

                // Focus style audit - skip, handled by state testing instead
                // (checking default state styles doesn't detect :focus-visible rules)
            }
        }
    }

    // ── Non-text contrast (UI component boundaries) ──
    const uiComponents = document.querySelectorAll('input, select, textarea, button, [role="button"]');
    for (const el of uiComponents) {
        const style = getComputedStyle(el);
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) continue;

        const elBg = rgbToHex(style.backgroundColor);
        const parentBg = getEffectiveBg(el.parentElement);
        const borderColor = rgbToHex(style.borderColor || style.borderTopColor);
        const hasBorder = style.borderStyle !== 'none' && style.borderWidth !== '0px';

        if (elBg && parentBg) {
            const bgRatio = getContrastRatio(elBg, parentBg);
            const selector = el.tagName.toLowerCase()
                + (el.className ? '.' + el.className.toString().split(' ')[0] : '');

            results.non_text_contrast.push({
                element: selector,
                text: (el.textContent || el.placeholder || '').trim().substring(0, 30),
                component_bg: elBg,
                adjacent_bg: parentBg,
                bg_ratio: bgRatio,
                has_border: hasBorder,
                border_color: hasBorder ? borderColor : null,
                border_ratio: hasBorder && borderColor ? getContrastRatio(borderColor, parentBg) : null,
                passes_3_to_1: (bgRatio >= 3) || (hasBorder && borderColor && getContrastRatio(borderColor, parentBg) >= 3),
            });
        }
    }

    // ── Assemble results ──
    results.colors = {
        text: Object.entries(colorCounts)
            .sort((a, b) => b[1] - a[1]).slice(0, 15)
            .map(([color, count]) => ({ color, count })),
        background: Object.entries(bgColorCounts)
            .sort((a, b) => b[1] - a[1]).slice(0, 15)
            .map(([color, count]) => ({ color, count })),
    };

    results.fonts = {
        sizes: Object.entries(fontSizes)
            .sort((a, b) => b[1] - a[1]).slice(0, 15)
            .map(([size, count]) => ({ size, count })),
        families: Object.entries(fontFamilies)
            .sort((a, b) => b[1] - a[1]).slice(0, 5)
            .map(([family, count]) => ({ family, count })),
    };

    results.spacing_values = Object.entries(spacingValues)
        .sort((a, b) => b[1] - a[1]).slice(0, 20)
        .map(([value, count]) => ({ value, count }));

    results.contrast_pairs = contrastPairs
        .sort((a, b) => a.ratio - b.ratio).slice(0, 20);

    results.interactive_elements = interactiveElements.slice(0, 30);
    // focus_audit removed - :focus-visible detection handled via
    // stylesheet rule scanning (html_structure.has_global_focus_visible)
    // and interactive state testing (_test_interactive_states)

    // Layout
    const body = document.body;
    const bodyStyle = getComputedStyle(body);
    results.layout = {
        viewport_width: window.innerWidth,
        viewport_height: window.innerHeight,
        body_font_size: bodyStyle.fontSize,
        body_line_height: bodyStyle.lineHeight,
        body_font_family: bodyStyle.fontFamily.split(',')[0].trim().replace(/['"]/g, ''),
        body_bg: rgbToHex(bodyStyle.backgroundColor),
    };

    return results;
}
"""


STATE_TEST_SCRIPT = """
(selector) => {
    const el = document.querySelector(selector);
    if (!el) return null;
    const style = getComputedStyle(el);
    return {
        backgroundColor: style.backgroundColor,
        color: style.color,
        borderColor: style.borderColor,
        outline: style.outline,
        outlineStyle: style.outlineStyle,
        boxShadow: style.boxShadow,
        opacity: style.opacity,
        cursor: style.cursor,
        transform: style.transform,
        textDecoration: style.textDecoration,
    };
}
"""


async def _test_interactive_states(page) -> list[dict]:
    """Test hover and focus states on interactive elements by triggering them."""
    results = []

    # Wait for styles to fully load before testing
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(500)

    # Get interactive elements with unique selectors
    elements = await page.evaluate("""
        () => {
            const els = document.querySelectorAll('button, a, input, select, [role="button"], [role="tab"]');
            const seen = new Set();
            const targets = [];
            for (const el of els) {
                const rect = el.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;
                if (el.closest('[style*="display: none"]')) continue;

                // Build a unique selector
                let selector = el.tagName.toLowerCase();
                if (el.id) selector += '#' + el.id;
                else if (el.className) selector += '.' + el.className.toString().split(' ').filter(c => c).join('.');

                if (seen.has(selector)) continue;
                seen.add(selector);

                targets.push({
                    selector: selector,
                    text: (el.textContent || el.placeholder || '').trim().substring(0, 30),
                    tag: el.tagName.toLowerCase(),
                    x: Math.round(rect.x + rect.width / 2),
                    y: Math.round(rect.y + rect.height / 2),
                });
                if (targets.length >= 15) break;
            }
            return targets;
        }
    """)

    for el_info in elements:
        selector = el_info["selector"]
        try:
            # Capture default state
            default_state = await page.evaluate(STATE_TEST_SCRIPT, selector)
            if not default_state:
                continue

            # Test hover state — wait for CSS transitions to complete
            await page.hover(selector, timeout=2000)
            await page.wait_for_timeout(300)
            hover_state = await page.evaluate(STATE_TEST_SCRIPT, selector)

            # Test focus state
            await page.focus(selector, timeout=2000)
            await page.wait_for_timeout(300)
            focus_state = await page.evaluate(STATE_TEST_SCRIPT, selector)

            # Compare states
            hover_changed = hover_state and any(
                default_state.get(k) != hover_state.get(k)
                for k in ["backgroundColor", "color", "borderColor", "boxShadow",
                           "opacity", "cursor", "transform", "textDecoration"]
            )
            focus_changed = focus_state and any(
                default_state.get(k) != focus_state.get(k)
                for k in ["backgroundColor", "color", "borderColor", "outline",
                           "outlineStyle", "boxShadow"]
            )

            hover_changes = {}
            if hover_changed and hover_state:
                for k in ["backgroundColor", "color", "borderColor", "cursor"]:
                    if default_state.get(k) != hover_state.get(k):
                        hover_changes[k] = {"from": default_state[k], "to": hover_state[k]}

            focus_changes = {}
            if focus_changed and focus_state:
                for k in ["outline", "outlineStyle", "boxShadow", "borderColor"]:
                    if default_state.get(k) != focus_state.get(k):
                        focus_changes[k] = {"from": default_state[k], "to": focus_state[k]}

            results.append({
                "selector": selector,
                "text": el_info["text"],
                "has_hover_state": hover_changed,
                "has_focus_state": focus_changed,
                "hover_changes": hover_changes,
                "focus_changes": focus_changes,
                "cursor_on_hover": hover_state.get("cursor", "auto") if hover_state else "auto",
            })

            # Reset by moving mouse away
            await page.mouse.move(0, 0)
            await page.evaluate("document.activeElement?.blur()")

        except Exception:
            continue

    return results


def _compress_screenshot(path: str, max_bytes: int = 4_500_000) -> None:
    """Compress a screenshot if it exceeds the max size (default 4.5MB for API limits)."""
    from PIL import Image
    file_size = Path(path).stat().st_size
    if file_size <= max_bytes:
        return

    img = Image.open(path)
    # Resize to reduce file size — scale down proportionally
    scale = (max_bytes / file_size) ** 0.5
    new_width = int(img.width * scale)
    new_height = int(img.height * scale)
    img = img.resize((new_width, new_height), Image.LANCZOS)

    # Save as JPEG with quality reduction if still too large
    if path.endswith(".png"):
        img.save(path, optimize=True)
        if Path(path).stat().st_size > max_bytes:
            jpg_path = path.replace(".png", ".jpg")
            img.save(jpg_path, "JPEG", quality=80)
            Path(path).unlink()
            Path(jpg_path).rename(path)
    else:
        img.save(path, "JPEG", quality=80)


async def _capture_page(page, output_path: str) -> tuple[str, dict]:
    """Capture screenshot and extract DOM data from a single page."""
    # Use viewport-only screenshot to avoid massive full-page captures
    await page.screenshot(path=output_path, full_page=False)
    _compress_screenshot(output_path)
    text = await page.inner_text("body")
    try:
        dom_data = await page.evaluate(DOM_EXTRACTION_SCRIPT)
    except Exception:
        dom_data = {}

    # Test interactive states
    try:
        state_results = await _test_interactive_states(page)
        dom_data["state_tests"] = state_results
    except Exception:
        dom_data["state_tests"] = []

    # Run axe-core accessibility audit
    try:
        from src.analysis.axe_runner import run_axe_on_page
        axe_result = await run_axe_on_page(page)
        dom_data["axe_results"] = {
            "violations": axe_result.violations,
            "passes": [p.get("id") for p in axe_result.passes],
            "incomplete": axe_result.incomplete,
            "violation_count": axe_result.violation_count,
            "pass_count": axe_result.pass_count,
            "critical_count": axe_result.critical_count,
            "serious_count": axe_result.serious_count,
            "error": axe_result.error,
        }
    except Exception:
        dom_data["axe_results"] = {"error": "axe-core not available", "violations": [], "passes": []}

    return text, dom_data


def _is_blocked_page(text: str, url: str) -> bool:
    """Detect if the page is an access denied / bot block page."""
    text_lower = text.lower().strip()
    block_indicators = [
        "access denied",
        "403 forbidden",
        "you don't have permission",
        "blocked",
        "captcha",
        "verify you are human",
        "please enable javascript",
        "checking your browser",
        "just a moment",
        "ray id",
    ]
    # Short page with block language = likely blocked
    if len(text_lower) < 500:
        for indicator in block_indicators:
            if indicator in text_lower:
                return True
    # Title-only pages with errors
    if len(text_lower) < 100 and any(code in text_lower for code in ["403", "401", "access"]):
        return True
    return False


async def _capture(url: str, output_path: str, viewport_width: int = 1440, viewport_height: int = 900) -> tuple[str, dict]:
    async with async_playwright() as p:
        browser = await _launch_browser(p)
        page = await _new_stealth_page(browser, viewport_width, viewport_height)
        await page.goto(url, wait_until="networkidle", timeout=30000)
        text, dom_data = await _capture_page(page, output_path)

        # Check for access denied
        dom_data["_blocked"] = _is_blocked_page(text, url)

        await browser.close()
    return text, dom_data


async def _crawl_app(
    url: str,
    output_dir: str,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    max_pages: int = 10,
) -> list[dict]:
    """Crawl an app by discovering and clicking navigation links.

    Returns a list of page captures: [{url, label, image_path, page_text, dom_data}]
    """
    from urllib.parse import urlparse, urljoin

    base = urlparse(url)
    base_origin = f"{base.scheme}://{base.netloc}"
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    pages_captured = []
    visited_urls = set()
    visited_paths = set()

    async with async_playwright() as p:
        browser = await _launch_browser(p)
        page = await _new_stealth_page(browser, viewport_width, viewport_height)

        # Capture the initial page
        await page.goto(url, wait_until="networkidle", timeout=30000)
        initial_path = urlparse(page.url).path or "/"
        visited_urls.add(page.url)
        visited_paths.add(initial_path)

        screenshot_path = str(output / "page-000-home.png")
        text, dom_data = await _capture_page(page, screenshot_path)

        # Check for access denied on first page
        if _is_blocked_page(text, url):
            dom_data["_blocked"] = True
            pages_captured.append({
                "url": page.url,
                "label": "Home",
                "image_path": screenshot_path,
                "page_text": text,
                "dom_data": dom_data,
            })
            await browser.close()
            return pages_captured

        pages_captured.append({
            "url": page.url,
            "label": "Home",
            "image_path": screenshot_path,
            "page_text": text,
            "dom_data": dom_data,
        })

        # Discover navigation links
        nav_targets = await page.evaluate("""
            () => {
                const targets = [];
                const seen = new Set();

                // Find links and buttons in nav-like containers
                const navElements = document.querySelectorAll(
                    'nav a, nav button, header a, header button, footer a, footer button, '
                    + '[role="navigation"] a, [role="navigation"] button, '
                    + '[role="tablist"] [role="tab"], '
                    + '[class*="nav"] a, [class*="nav"] button, '
                    + '[class*="tab"] a, [class*="tab"] button, '
                    + '[class*="bar"] a, [class*="bar"] button, '
                    + '[class*="bottom"] a, [class*="bottom"] button, '
                    + '[class*="sidebar"] a, [class*="sidebar"] button, '
                    + '[class*="menu"] a, [class*="menu"] button'
                );

                for (const el of navElements) {
                    const text = el.textContent?.trim();
                    if (!text || text.length > 30 || text.length < 2) continue;

                    // Skip hidden elements (critical for responsive layouts)
                    const rect = el.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;
                    const elStyle = getComputedStyle(el);
                    if (elStyle.display === 'none' || elStyle.visibility === 'hidden') continue;
                    if (elStyle.opacity === '0') continue;

                    const href = el.getAttribute('href');
                    const key = text.toLowerCase();

                    if (seen.has(key)) continue;
                    seen.add(key);

                    // Skip external links, anchors, and javascript:
                    if (href && (href.startsWith('http') && !href.startsWith(location.origin))) continue;
                    if (href === '#' || href?.startsWith('javascript:')) continue;

                    targets.push({
                        text: text,
                        href: href || null,
                        tag: el.tagName.toLowerCase(),
                        selector: el.tagName.toLowerCase()
                            + (el.className ? '.' + el.className.toString().split(' ')[0] : ''),
                    });
                }

                return targets;
            }
        """)

        # Filter to primary nav targets (skip filter pills, muscle groups, etc.)
        primary_nav = []
        seen_labels = set()
        for target in nav_targets:
            label = target["text"].strip()
            label_lower = label.lower()
            # Skip duplicate labels and filter-type buttons
            if label_lower in seen_labels:
                continue
            # Skip very short labels that are likely filters (but keep nav-like ones)
            if len(label) <= 2 and not target.get("href"):
                continue
            seen_labels.add(label_lower)
            primary_nav.append(target)

        # Get initial page content fingerprint for change detection
        async def _get_content_fingerprint():
            return await page.evaluate("""
                () => {
                    const main = document.querySelector('main, [class*="main"], [class*="content"], [class*="page"]');
                    const target = main || document.body;
                    return target.innerHTML.substring(0, 500);
                }
            """)

        initial_fingerprint = await _get_content_fingerprint()

        # Navigate to each discovered page
        page_num = 1
        for target in primary_nav:
            if page_num >= max_pages:
                break

            label = target["text"].strip()
            href = target.get("href")
            selector = target.get("selector", "")

            # Skip if already visited (by label)
            if label.lower() in {p["label"].lower() for p in pages_captured}:
                continue

            try:
                # Take a content snapshot before clicking
                pre_click_fingerprint = await _get_content_fingerprint()

                if href and not href.startswith('#') and href != '/':
                    await page.goto(urljoin(base_origin, href), wait_until="networkidle", timeout=15000)
                else:
                    # SPA navigation: click the button and wait for content change
                    # Use a more robust selector strategy
                    element = None

                    # Try exact text match on buttons first
                    buttons = page.locator(f"button:has-text('{label}')")
                    count = await buttons.count()
                    if count > 0:
                        # Click the first visible, non-active button
                        for i in range(count):
                            btn = buttons.nth(i)
                            if not await btn.is_visible():
                                continue
                            classes = await btn.get_attribute("class") or ""
                            if "active" not in classes:
                                element = btn
                                break
                        # Fallback: first visible button (even if active)
                        if not element:
                            for i in range(count):
                                btn = buttons.nth(i)
                                if await btn.is_visible():
                                    element = btn
                                    break
                    if not element:
                        # Try links
                        links = page.locator(f"a:has-text('{label}')")
                        if await links.count() > 0:
                            element = links.first

                    if element:
                        await element.click()
                        # Wait for content to change (SPA transition)
                        try:
                            await page.wait_for_timeout(500)
                            await page.wait_for_load_state("networkidle", timeout=10000)
                        except Exception:
                            await page.wait_for_timeout(1000)

                # Check if content actually changed (for SPAs the URL may be the same)
                post_click_fingerprint = await _get_content_fingerprint()
                new_url = page.url

                content_changed = post_click_fingerprint != pre_click_fingerprint
                url_changed = new_url not in visited_urls

                if not content_changed and not url_changed:
                    # Nothing changed, skip
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                    continue

                visited_urls.add(new_url)

                # Capture this page
                safe_label = label.lower().replace(" ", "-")[:20]
                screenshot_path = str(output / f"page-{page_num:03d}-{safe_label}.png")
                text, dom_data = await _capture_page(page, screenshot_path)

                pages_captured.append({
                    "url": new_url,
                    "label": label,
                    "image_path": screenshot_path,
                    "page_text": text,
                    "dom_data": dom_data,
                })
                page_num += 1

                # Go back to start for next navigation
                await page.goto(url, wait_until="networkidle", timeout=15000)

            except Exception:
                # Navigation failed, continue to next target
                try:
                    await page.goto(url, wait_until="networkidle", timeout=15000)
                except Exception:
                    pass
                continue

        await browser.close()

    return pages_captured


def capture_url(url: str, output_path: str = "output/screenshot.png", viewport_width: int = 1440, viewport_height: int = 900) -> tuple[str, str, dict]:
    """Capture a screenshot of a URL. Returns (screenshot_path, extracted_text, dom_data)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    text, dom_data = asyncio.run(_capture(url, output_path, viewport_width=viewport_width, viewport_height=viewport_height))
    return output_path, text, dom_data


def crawl_app(url: str, output_dir: str = "output/pages", max_pages: int = 10, viewport_width: int = 1440, viewport_height: int = 900) -> list[dict]:
    """Crawl an app and capture multiple pages. Returns list of page capture dicts."""
    return asyncio.run(_crawl_app(url, output_dir, max_pages=max_pages, viewport_width=viewport_width, viewport_height=viewport_height))
