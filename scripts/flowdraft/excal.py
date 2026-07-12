"""
flowdraft.excal
---------------
The ``Excal`` class — a lightweight Excalidraw JSON document builder.

Every drawing primitive (rect, ellipse, line, text, …) appends a JSON element
to ``Excal.elements``.  Call ``Excal.write(path)`` to persist the file.
"""

import json
import random

from .constants import THEME, UPDATED
from .fonts import has_cjk


class Excal:
    """Builds an Excalidraw JSON document incrementally.

    Attributes:
        width:    Canvas width in logical pixels.
        height:   Canvas height in logical pixels.
        elements: List of Excalidraw element dicts.
        count:    Running element counter (used for unique IDs).
        rng:      Seeded random number generator for deterministic seeds/nonces.
    """

    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.elements: list = []
        self.count: int = 0
        self.rng = random.Random(2069769416930414980)

    # ------------------------------------------------------------------
    # Internal base builder
    # ------------------------------------------------------------------
    def base(
        self,
        prefix: str,
        kind: str,
        x: float,
        y: float,
        w: float,
        h: float,
        stroke: str,
        fill: str = "transparent",
        stroke_width: float = 2,
        stroke_style: str = "solid",
        roundness=None,
        radius=None,
        opacity=None,
    ) -> dict:
        """Create and append a base element dict.

        Args:
            prefix:       Short string prefix for the element ID (e.g. "rect").
            kind:         Excalidraw element type string (e.g. "rectangle").
            x, y:         Top-left in logical canvas coordinates.
            w, h:         Width and height.
            stroke:       Stroke colour hex string.
            fill:         Fill colour hex string or "transparent".
            stroke_width: Stroke width.
            stroke_style: "solid" | "dashed" | "dotted".
            roundness:    Excalidraw roundness dict or None.
            radius:       Private ``_radius`` override stored on the element.
            opacity:      Private ``_opacity`` stored on the element (0-1 float).

        Returns:
            The newly created element dict.
        """
        self.count += 1
        element = {
            "id": f"{prefix}-{self.count:04d}",
            "type": kind,
            "x": round(x, 2),
            "y": round(y, 2),
            "width": round(w, 2),
            "height": round(h, 2),
            "angle": 0,
            "strokeColor": stroke,
            "backgroundColor": fill or "transparent",
            "fillStyle": "solid",
            "strokeWidth": stroke_width,
            "strokeStyle": stroke_style,
            "roughness": 1,
            "opacity": 100,
            "groupIds": [],
            "frameId": None,
            "index": f"a{self.count:04d}",
            "roundness": roundness,
            "seed": self.rng.randint(1, 2147483646),
            "version": 1,
            "versionNonce": self.rng.randint(1, 2147483646),
            "isDeleted": False,
            "boundElements": None,
            "updated": UPDATED,
            "link": None,
            "locked": False,
        }
        if radius is not None:
            element["_radius"] = radius
        if opacity is not None:
            element["_opacity"] = opacity
        self.elements.append(element)
        return element

    # ------------------------------------------------------------------
    # Public shape builders
    # ------------------------------------------------------------------
    def rect(
        self,
        x: float, y: float, w: float, h: float,
        stroke: str,
        fill: str = "transparent",
        width: float = 2,
        style: str = "solid",
        radius=None,
        opacity=None,
    ) -> dict:
        """Append a rectangle element."""
        return self.base(
            "rect", "rectangle", x, y, w, h, stroke, fill, width, style,
            {"type": 3}, radius=radius, opacity=opacity,
        )

    def ellipse(
        self,
        x: float, y: float, w: float, h: float,
        stroke: str,
        fill: str = "transparent",
        width: float = 2,
        style: str = "solid",
        opacity=None,
    ) -> dict:
        """Append an ellipse element."""
        return self.base(
            "ellipse", "ellipse", x, y, w, h, stroke, fill, width, style,
            None, opacity=opacity,
        )

    def diamond(
        self,
        x: float, y: float, w: float, h: float,
        stroke: str,
        fill: str = "transparent",
        width: float = 2,
        opacity=None,
    ) -> dict:
        """Append a diamond element."""
        return self.base(
            "diamond", "diamond", x, y, w, h, stroke, fill, width, "solid",
            {"type": 2}, opacity=opacity,
        )

    def text(
        self,
        text: str,
        x: float, y: float, w: float, h: float,
        size: float,
        color: str,
        align: str = "left",
        bold: bool = False,
        hand: bool = False,
        opacity=None,
    ) -> dict:
        """Append a text element."""
        from . import constants as _c
        hand = getattr(_c, "HAND", True)

        element = self.base(
            "text", "text", x, y, w, h, color, "transparent", 1, "solid",
            None, opacity=opacity,
        )
        element.update({
            "text": text,
            "fontSize": int(round(size)),
            "fontFamily": 5 if hand else 1,
            "textAlign": align,
            "verticalAlign": "top",
            "baseline": int(round(size * 1.25)),
            "containerId": None,
            "originalText": text,
            "lineHeight": 1.25,
            "_bold": bold,
            "_hand": hand,
            "_cjk": has_cjk(text),
        })
        return element

    def line(
        self,
        points: list,
        stroke: str,
        width: float = 2,
        style: str = "solid",
        arrow: bool = False,
        fill: str = "transparent",
        opacity=None,
    ) -> dict:
        """Append a line or arrow element.

        Args:
            points: List of ``(x, y)`` tuples in logical canvas coordinates.
            stroke: Stroke colour hex string.
            width:  Stroke width.
            style:  "solid" | "dashed" | "dotted".
            arrow:  If True, the element type is "arrow" instead of "line".
            fill:   Fill colour for closed paths.
            opacity: Optional 0-1 transparency.

        Returns:
            The newly created element dict.
        """
        kind = "arrow" if arrow else "line"
        min_x = min(px for px, _ in points)
        min_y = min(py for _, py in points)
        max_x = max(px for px, _ in points)
        max_y = max(py for _, py in points)
        element = self.base(
            kind, kind,
            min_x, min_y,
            max_x - min_x,
            max_y - min_y,
            stroke, fill or "transparent", width, style, {"type": 2},
            opacity=opacity,
        )
        element["points"] = [
            [round(px - min_x, 2), round(py - min_y, 2)] for px, py in points
        ]
        element["startBinding"] = None
        element["endBinding"] = None
        return element

    # ------------------------------------------------------------------
    # File I/O
    # ------------------------------------------------------------------
    def write(self, path) -> None:
        """Serialise the document to an ``.excalidraw`` JSON file.

        Args:
            path: A ``pathlib.Path`` (or any object with ``.write_text``).
        """
        data = {
            "type": "excalidraw",
            "version": 2,
            "source": "https://excalidraw.com",
            "elements": self.elements,
            "appState": {
                "viewBackgroundColor": THEME["bg"],
                "gridSize": 20,
                "currentItemFontFamily": 5,
            },
            "files": {},
        }
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
