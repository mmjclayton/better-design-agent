from dataclasses import dataclass, field
from enum import Enum


class InputType(Enum):
    SCREENSHOT = "screenshot"
    URL = "url"
    TEXT = "text"
    FIGMA = "figma"


@dataclass
class PageCapture:
    """Data captured from a single page/view."""
    url: str
    label: str
    image_path: str
    page_text: str = ""
    dom_data: dict = field(default_factory=dict)


@dataclass
class DesignInput:
    type: InputType
    image_path: str | None = None
    page_text: str | None = None
    url: str | None = None
    dom_data: dict = field(default_factory=dict)
    pages: list[PageCapture] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
