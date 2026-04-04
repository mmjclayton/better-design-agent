import asyncio
import json
from pathlib import Path

from playwright.async_api import async_playwright

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

    function rgbToHex(rgb) {
        if (!rgb || rgb === 'transparent' || rgb === 'rgba(0, 0, 0, 0)') return null;
        const match = rgb.match(/rgba?\\((\\d+),\\s*(\\d+),\\s*(\\d+)/);
        if (!match) return rgb;
        return '#' + [match[1], match[2], match[3]]
            .map(x => parseInt(x).toString(16).padStart(2, '0'))
            .join('');
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
        let current = el;
        while (current && current !== document.documentElement) {
            const bg = getComputedStyle(current).backgroundColor;
            const hex = rgbToHex(bg);
            if (hex) return hex;
            current = current.parentElement;
        }
        return '#ffffff';
    }

    // ── CSS Custom Properties (Design Tokens) ──
    const rootStyles = getComputedStyle(document.documentElement);
    const tokenCategories = { color: [], spacing: [], radius: [], font: [], other: [] };

    for (const sheet of document.styleSheets) {
        try {
            for (const rule of sheet.cssRules) {
                if (rule.selectorText === ':root' || rule.selectorText === ':root, :host') {
                    for (const prop of rule.style) {
                        if (prop.startsWith('--')) {
                            const value = rule.style.getPropertyValue(prop).trim();
                            const entry = { name: prop, value: value };

                            if (/color|bg|text|accent|surface|border|success|warning|danger|primary|secondary/.test(prop)) {
                                tokenCategories.color.push(entry);
                            } else if (/space|gap|padding|margin/.test(prop)) {
                                tokenCategories.spacing.push(entry);
                            } else if (/radius|round/.test(prop)) {
                                tokenCategories.radius.push(entry);
                            } else if (/font|text|size/.test(prop)) {
                                tokenCategories.font.push(entry);
                            } else {
                                tokenCategories.other.push(entry);
                            }
                        }
                    }
                }
            }
        } catch (e) { /* cross-origin stylesheet */ }
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

    results.html_structure = htmlAudit;

    // ── Element Analysis ──
    const contrastPairs = [];
    const seen = new Set();
    const interactiveElements = [];
    const focusAudit = [];

    for (const el of allElements) {
        const style = getComputedStyle(el);
        if (style.display === 'none' || style.visibility === 'hidden') continue;

        const color = rgbToHex(style.color);
        const bgColor = rgbToHex(style.backgroundColor);
        if (color) colorCounts[color] = (colorCounts[color] || 0) + 1;
        if (bgColor) bgColorCounts[bgColor] = (bgColorCounts[bgColor] || 0) + 1;

        // Fonts
        const fontSize = style.fontSize;
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

                // Focus style audit - check if element has custom focus styles
                const focusOutline = style.outlineStyle;
                const focusBoxShadow = style.boxShadow;
                const hasCustomFocus = (focusOutline && focusOutline !== 'none')
                    || (focusBoxShadow && focusBoxShadow !== 'none');
                focusAudit.push({
                    element: selector,
                    text: (el.textContent || '').trim().substring(0, 30),
                    has_outline: focusOutline !== 'none',
                    outline_style: focusOutline,
                    has_box_shadow: focusBoxShadow !== 'none',
                });
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
    results.focus_audit = focusAudit.slice(0, 30);

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

            # Test hover state
            await page.hover(selector, timeout=2000)
            await page.wait_for_timeout(100)
            hover_state = await page.evaluate(STATE_TEST_SCRIPT, selector)

            # Test focus state
            await page.focus(selector, timeout=2000)
            await page.wait_for_timeout(100)
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


async def _capture_page(page, output_path: str) -> tuple[str, dict]:
    """Capture screenshot and extract DOM data from a single page."""
    await page.screenshot(path=output_path, full_page=True)
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

    return text, dom_data


async def _capture(url: str, output_path: str, viewport_width: int = 1440) -> tuple[str, dict]:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": viewport_width, "height": 900})
        await page.goto(url, wait_until="networkidle", timeout=30000)
        text, dom_data = await _capture_page(page, output_path)
        await browser.close()
    return text, dom_data


async def _crawl_app(
    url: str,
    output_dir: str,
    viewport_width: int = 1440,
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
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": viewport_width, "height": 900})

        # Capture the initial page
        await page.goto(url, wait_until="networkidle", timeout=30000)
        initial_path = urlparse(page.url).path or "/"
        visited_urls.add(page.url)
        visited_paths.add(initial_path)

        screenshot_path = str(output / "page-000-home.png")
        text, dom_data = await _capture_page(page, screenshot_path)
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
                    'nav a, nav button, header a, header button, '
                    + '[role="navigation"] a, [role="navigation"] button, '
                    + '[role="tablist"] [role="tab"], '
                    + '[class*="nav"] a, [class*="nav"] button, '
                    + '[class*="tab"] a, [class*="tab"] button, '
                    + '[class*="sidebar"] a, [class*="sidebar"] button, '
                    + '[class*="menu"] a, [class*="menu"] button'
                );

                for (const el of navElements) {
                    const text = el.textContent?.trim();
                    if (!text || text.length > 30 || text.length < 2) continue;

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
            # Skip very short labels that are likely filters
            if len(label) <= 3 and not target.get("href"):
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
                        # Click the first non-active one, or the first one
                        for i in range(count):
                            btn = buttons.nth(i)
                            classes = await btn.get_attribute("class") or ""
                            if "active" not in classes:
                                element = btn
                                break
                        if not element:
                            element = buttons.first
                    else:
                        # Try links
                        element = page.locator(f"a:has-text('{label}')").first

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


def capture_url(url: str, output_path: str = "output/screenshot.png") -> tuple[str, str, dict]:
    """Capture a screenshot of a URL. Returns (screenshot_path, extracted_text, dom_data)."""
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    text, dom_data = asyncio.run(_capture(url, output_path))
    return output_path, text, dom_data


def crawl_app(url: str, output_dir: str = "output/pages", max_pages: int = 10) -> list[dict]:
    """Crawl an app and capture multiple pages. Returns list of page capture dicts."""
    return asyncio.run(_crawl_app(url, output_dir, max_pages=max_pages))
