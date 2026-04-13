import os
from pathlib import Path

from src.input.models import DesignInput, InputType, PageCapture
from src.input.screenshot import capture_url, crawl_app


DEFAULT_AUTH_PATH = Path(".design-intel/auth.json")


def resolve_auth_path(explicit: str | None = None) -> str | None:
    """Pick the auth file to use: env disable > explicit > env override > default > none.

    Environment variables:
      - DESIGN_INTEL_NO_AUTH=1  → always return None (opt out)
      - DESIGN_INTEL_AUTH=path  → use this path if it exists
    """
    if os.environ.get("DESIGN_INTEL_NO_AUTH"):
        return None
    if explicit:
        p = Path(explicit)
        return str(p) if p.exists() else None
    env_path = os.environ.get("DESIGN_INTEL_AUTH")
    if env_path:
        p = Path(env_path)
        return str(p) if p.exists() else None
    if DEFAULT_AUTH_PATH.exists():
        return str(DEFAULT_AUTH_PATH)
    return None


def process_image(image_path: str) -> DesignInput:
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    return DesignInput(type=InputType.SCREENSHOT, image_path=str(path.resolve()))


def process_url(
    url: str,
    crawl: bool = False,
    max_pages: int = 10,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    auth_path: str | None = None,
) -> DesignInput:
    # Use viewport-specific output paths to avoid overwriting between desktop/mobile runs
    vp_suffix = f"{viewport_width}x{viewport_height}"

    if crawl:
        page_dicts = crawl_app(url, output_dir=f"output/pages-{vp_suffix}", max_pages=max_pages, viewport_width=viewport_width, viewport_height=viewport_height, storage_state_path=auth_path)
        if not page_dicts:
            raise RuntimeError(f"Failed to capture any pages from {url}")

        # First page is the primary
        first = page_dicts[0]
        pages = [
            PageCapture(
                url=p["url"],
                label=p["label"],
                image_path=p["image_path"],
                page_text=p["page_text"],
                dom_data=p["dom_data"],
            )
            for p in page_dicts
        ]

        return DesignInput(
            type=InputType.URL,
            image_path=first["image_path"],
            page_text=first["page_text"],
            url=url,
            dom_data=first["dom_data"],
            pages=pages,
        )

    screenshot_path, page_text, dom_data = capture_url(url, output_path=f"output/screenshot-{vp_suffix}.png", viewport_width=viewport_width, viewport_height=viewport_height, storage_state_path=auth_path)
    return DesignInput(
        type=InputType.URL,
        image_path=screenshot_path,
        page_text=page_text,
        url=url,
        dom_data=dom_data,
    )


def process_text(description: str) -> DesignInput:
    return DesignInput(type=InputType.TEXT, page_text=description)


def process_input(
    image: str | None = None,
    url: str | None = None,
    describe: str | None = None,
    crawl: bool = False,
    max_pages: int = 10,
    viewport_width: int = 1440,
    viewport_height: int = 900,
    auth_path: str | None = None,
) -> DesignInput:
    if image:
        return process_image(image)
    if url:
        # Auto-detect saved auth session unless disabled via env var.
        resolved_auth = resolve_auth_path(auth_path)
        return process_url(url, crawl=crawl, max_pages=max_pages, viewport_width=viewport_width, viewport_height=viewport_height, auth_path=resolved_auth)
    if describe:
        return process_text(describe)
    raise ValueError("Provide one of: --image, --url, or --describe")
