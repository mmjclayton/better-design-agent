from pathlib import Path

from src.input.models import DesignInput, InputType, PageCapture
from src.input.screenshot import capture_url, crawl_app


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
) -> DesignInput:
    if crawl:
        page_dicts = crawl_app(url, max_pages=max_pages, viewport_width=viewport_width, viewport_height=viewport_height)
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

    screenshot_path, page_text, dom_data = capture_url(url, viewport_width=viewport_width, viewport_height=viewport_height)
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
) -> DesignInput:
    if image:
        return process_image(image)
    if url:
        return process_url(url, crawl=crawl, max_pages=max_pages, viewport_width=viewport_width, viewport_height=viewport_height)
    if describe:
        return process_text(describe)
    raise ValueError("Provide one of: --image, --url, or --describe")
