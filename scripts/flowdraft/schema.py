"""
flowdraft.schema
----------------
Validates and normalises FlowDraft **v2** spec JSON files.

Responsibilities
~~~~~~~~~~~~~~~~
* Enforce required / optional top-level keys with sane defaults.
* Normalise every element dict so downstream code never needs to guard
  against missing keys.
* Flatten nested ``children`` / ``footer`` into the top-level element
  list, assigning ``parent`` back-references.
* Validate that every connection and annotation endpoint references an
  element ID that actually exists.

Entry point
~~~~~~~~~~~
>>> from flowdraft.schema import validate_spec
>>> spec = validate_spec(raw_json_dict)

If anything is wrong a `SpecError` is raised with a human-readable message.
"""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional, Set

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

SUPPORTED_ELEMENT_TYPES: frozenset[str] = frozenset(
    {"card", "diamond", "panel", "input", "label", "group", "cylinder", "cloud", "ellipse"}
)

SUPPORTED_CONNECTION_STYLES: frozenset[str] = frozenset(
    {"solid", "dashed", "dotted"}
)

SUPPORTED_PORTS: frozenset[str] = frozenset(
    {"top", "bottom", "left", "right"}
)

SUPPORTED_ANNOTATION_POSITIONS: frozenset[str] = frozenset(
    {"top", "bottom", "left", "right", "midpoint",
     "top-left", "top-right", "bottom-left", "bottom-right",
     "top-label", "center"}
)

SUPPORTED_THEMES: frozenset[str] = frozenset(
    {"dark", "light", "white"}
)

DEFAULT_CANVAS: Dict[str, int] = {
    "width": 1920,
    "height": 1440,
}


# ──────────────────────────────────────────────────────────────────────
# Exception
# ──────────────────────────────────────────────────────────────────────

class SpecError(Exception):
    """Raised when a v2 spec fails validation.

    Attributes:
        path:    JSONPath-style breadcrumb showing *where* the error is
                 (e.g. ``"elements[2].connections[0].to"``).
        reason:  Human-readable explanation.
    """

    def __init__(self, reason: str, *, path: str = "") -> None:
        self.path = path
        self.reason = reason
        prefix = f"[{path}] " if path else ""
        super().__init__(f"{prefix}{reason}")


# ──────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────

def _require(obj: dict, key: str, *, path: str, expected: str = "value") -> Any:
    """Raise :class:`SpecError` if *key* is missing from *obj*."""
    if key not in obj:
        raise SpecError(
            f"Missing required field '{key}' (expected {expected}).",
            path=path,
        )
    return obj[key]


def _require_type(
    value: Any,
    expected_type: type,
    *,
    path: str,
    label: str = "value",
) -> None:
    """Raise :class:`SpecError` if *value* is not of *expected_type*."""
    if not isinstance(value, expected_type):
        actual = type(value).__name__
        raise SpecError(
            f"'{label}' must be {expected_type.__name__}, got {actual}.",
            path=path,
        )


def _one_of(
    value: Any,
    choices: frozenset[str],
    *,
    path: str,
    label: str = "value",
) -> None:
    """Raise :class:`SpecError` if *value* is not in *choices*."""
    if value not in choices:
        allowed = ", ".join(sorted(choices))
        raise SpecError(
            f"'{label}' must be one of [{allowed}], got '{value}'.",
            path=path,
        )


def _gen_id(base: str, existing_ids: Set[str]) -> str:
    """Generate a unique ID derived from *base* that is not in *existing_ids*.

    The first attempt is *base* itself; subsequent attempts append ``_2``,
    ``_3``, etc.
    """
    candidate = base
    counter = 2
    while candidate in existing_ids:
        candidate = f"{base}_{counter}"
        counter += 1
    return candidate


def _validate_style_dict(style_dict: Any, path: str) -> None:
    if not isinstance(style_dict, dict):
        raise SpecError("style must be a dictionary.", path=path)
    if "strokeWidth" in style_dict:
        val = style_dict["strokeWidth"]
        if not isinstance(val, (int, float)) or val < 0:
            raise SpecError(f"strokeWidth must be non-negative, got {val!r}.", path=f"{path}.strokeWidth")
    if "cornerRadius" in style_dict:
        val = style_dict["cornerRadius"]
        if not isinstance(val, (int, float)) or val < 0:
            raise SpecError(f"cornerRadius must be non-negative, got {val!r}.", path=f"{path}.cornerRadius")
    if "padding" in style_dict:
        pad = style_dict["padding"]
        if isinstance(pad, dict):
            for side in ("left", "right", "top", "bottom"):
                if side in pad:
                    val = pad[side]
                    if not isinstance(val, (int, float)) or val < 0:
                        raise SpecError(f"padding.{side} must be non-negative, got {val!r}.", path=f"{path}.padding.{side}")
        elif isinstance(pad, (int, float)):
            if pad < 0:
                raise SpecError(f"padding must be non-negative, got {pad!r}.", path=f"{path}.padding")
        elif pad is not None:
            raise SpecError("padding must be a number or a dictionary.", path=f"{path}.padding")


def _validate_layout_dict(layout_dict: Any, path: str) -> None:
    if not isinstance(layout_dict, dict):
        raise SpecError("layout must be a dictionary.", path=path)
    if "gap" in layout_dict:
        val = layout_dict["gap"]
        if not isinstance(val, (int, float)) or val < 0:
            raise SpecError(f"layout.gap must be non-negative, got {val!r}.", path=f"{path}.gap")
    if "max_cols" in layout_dict:
        val = layout_dict["max_cols"]
        if not isinstance(val, (int, float)) or val <= 0:
            raise SpecError(f"max_cols must be positive, got {val!r}.", path=f"{path}.max_cols")
    if "grid_cols" in layout_dict:
        val = layout_dict["grid_cols"]
        if not isinstance(val, (int, float)) or val <= 0:
            raise SpecError(f"grid_cols must be positive, got {val!r}.", path=f"{path}.grid_cols")
    if "padding" in layout_dict:
        pad = layout_dict["padding"]
        if isinstance(pad, dict):
            for side in ("left", "right", "top", "bottom"):
                if side in pad:
                    val = pad[side]
                    if not isinstance(val, (int, float)) or val < 0:
                        raise SpecError(f"padding.{side} must be non-negative, got {val!r}.", path=f"{path}.padding.{side}")
        elif isinstance(pad, (int, float)):
            if pad < 0:
                raise SpecError(f"padding must be non-negative, got {pad!r}.", path=f"{path}.padding")
        elif pad is not None:
            raise SpecError("padding must be a number or a dictionary.", path=f"{path}.padding")


# ──────────────────────────────────────────────────────────────────────
# Canvas
# ──────────────────────────────────────────────────────────────────────

def _normalise_canvas(raw: Optional[dict], path: str = "canvas") -> Dict[str, Any]:
    """Return a complete canvas dict, filling in defaults.

    Accepted optional keys beyond *width* / *height*:
    ``fps``, ``frames``, ``duration``, ``mode``.
    """
    if raw is None:
        raw = {}

    _require_type(raw, dict, path=path, label="canvas")

    canvas: Dict[str, Any] = {}
    canvas["width"] = raw.get("width", DEFAULT_CANVAS["width"])
    canvas["height"] = raw.get("height", DEFAULT_CANVAS["height"])

    for key in ("width", "height"):
        val = canvas[key]
        if not isinstance(val, (int, float)) or val <= 0:
            raise SpecError(
                f"canvas.{key} must be a positive number, got {val!r}.",
                path=f"{path}.{key}",
            )

    # Validate and normalize canvas.mode
    mode = raw.get("mode", "dynamic")
    if mode not in ("dynamic", "absolute", "graph"):
        raise SpecError(
            f"canvas.mode must be one of ['dynamic', 'absolute', 'graph'], got {mode!r}.",
            path=f"{path}.mode",
        )
    canvas["mode"] = mode

    # Temporal settings
    fps_val = raw.get("fps")
    dur_val = raw.get("duration")
    frames_val = raw.get("frames")

    # Validate types of provided variables
    if fps_val is not None:
        if not isinstance(fps_val, (int, float)):
            raise SpecError("canvas.fps must be a number.", path=f"{path}.fps")
        if fps_val <= 0:
            raise SpecError("canvas.fps must be a positive number.", path=f"{path}.fps")
    if dur_val is not None:
        if not isinstance(dur_val, (int, float)):
            raise SpecError("canvas.duration must be a number.", path=f"{path}.duration")
        if dur_val < 0:
            raise SpecError("canvas.duration must be a non-negative number.", path=f"{path}.duration")
    if frames_val is not None:
        if not isinstance(frames_val, (int, float)):
            raise SpecError("canvas.frames must be a number.", path=f"{path}.frames")
        if isinstance(frames_val, float):
            if abs(frames_val - int(frames_val)) > 1e-7:
                raise SpecError("canvas.frames must be an integer.", path=f"{path}.frames")
        if frames_val < 0:
            raise SpecError("canvas.frames must be a non-negative number.", path=f"{path}.frames")

    provided = []
    if fps_val is not None: provided.append("fps")
    if dur_val is not None: provided.append("duration")
    if frames_val is not None: provided.append("frames")

    if len(provided) <= 1:
        fps_val = 30.0
        dur_val = 3.0
        frames_val = 90
    elif len(provided) == 2:
        if fps_val is not None and dur_val is not None:
            frames_val = fps_val * dur_val
            if abs(frames_val - round(frames_val)) > 1e-5:
                raise SpecError(f"Solved frames ({frames_val}) is not close to an integer.", path=path)
            frames_val = int(round(frames_val))
        elif fps_val is not None and frames_val is not None:
            dur_val = float(frames_val) / fps_val
        elif dur_val is not None and frames_val is not None:
            fps_val = float(frames_val) / dur_val
    else: # len(provided) == 3
        if abs(frames_val - fps_val * dur_val) > 1e-5:
            raise SpecError(
                f"Inconsistent temporal animation settings: frames ({frames_val}) != fps ({fps_val}) * duration ({dur_val}).",
                path=path,
            )

    # Double check positive range
    if fps_val <= 0 or dur_val < 0 or frames_val < 0:
        raise SpecError("Temporal animation settings must be positive for FPS, and non-negative for duration and frames.", path=path)

    # Final conversion to correct types
    canvas["fps"] = float(fps_val)
    canvas["duration"] = float(dur_val)
    if abs(frames_val - round(frames_val)) > 1e-5:
        raise SpecError(f"frames must be an integer, got {frames_val}.", path=f"{path}.frames")
    canvas["frames"] = int(round(frames_val))

    return canvas


# ──────────────────────────────────────────────────────────────────────
# Elements
# ──────────────────────────────────────────────────────────────────────

_ELEMENT_DEFAULTS: Dict[str, Any] = {
    "title": "",
    "body": "",
    "icon": None,
    "style": {},
    "parent": None,
}


def _normalise_element(
    elem: dict,
    *,
    path: str,
    existing_ids: Set[str],
    parent_id: Optional[str] = None,
    parent_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Validate and normalise a single element dict.

    Returns a **list** because an element with ``children`` or ``footer``
    will be flattened into multiple top-level elements (the parent plus
    each child).

    Args:
        elem:         Raw element dict from the spec.
        path:         JSONPath breadcrumb for error messages.
        existing_ids: Mutable set tracking all IDs seen so far (used
                      for duplicate / auto-ID detection).
        parent_id:    If this element is a child, the ID of its parent.
        parent_type:  If this element is a child, the type of its parent.

    Returns:
        A list of normalised element dicts (parent first, then children).

    Raises:
        SpecError: On missing ``id``, missing ``type``, unknown type, or
                   duplicate ID.
    """
    _require_type(elem, dict, path=path, label="element")

    # --- id -----------------------------------------------------------
    _require(elem, "id", path=path, expected="unique string identifier")
    elem_id: str = elem["id"]
    _require_type(elem_id, str, path=f"{path}.id", label="id")

    if not elem_id.strip():
        raise SpecError("Element 'id' must not be empty.", path=f"{path}.id")

    if elem_id in existing_ids:
        raise SpecError(
            f"Duplicate element id '{elem_id}'.",
            path=f"{path}.id",
        )
    existing_ids.add(elem_id)

    # --- type ---------------------------------------------------------
    _require(elem, "type", path=path, expected="element type string")
    elem_type: str = elem["type"]
    _require_type(elem_type, str, path=f"{path}.type", label="type")
    _one_of(elem_type, SUPPORTED_ELEMENT_TYPES, path=f"{path}.type", label="type")

    # --- element structure check --------------------------------------
    if elem_type in ("card", "diamond", "input", "label"):
        if "children" in elem:
            raise SpecError(
                f"Leaf element '{elem_id}' of type '{elem_type}' cannot have nested children.",
                path=path,
            )

    # --- coordinate completeness & out_of_flow ------------------------
    has_x = elem.get("x") is not None
    has_y = elem.get("y") is not None
    if has_x != has_y:
        raise SpecError(
            f"Element '{elem_id}' has partial coordinates: x and y must both be specified or both omitted.",
            path=path,
        )

    # --- Build normalised element -------------------------------------
    normalised: Dict[str, Any] = {"id": elem_id, "type": elem_type}

    # Apply defaults for missing optional fields
    for key, default in _ELEMENT_DEFAULTS.items():
        value = elem.get(key, default)
        if key == "style":
            # Deep-copy to avoid shared mutation across elements
            value = dict(value) if isinstance(value, dict) else {}
        normalised[key] = value

    # Carry over the parent reference (set when recursing into children)
    normalised["parent"] = parent_id

    if has_x and has_y:
        if parent_id is not None:
            normalised["out_of_flow"] = True
        else:
            normalised["out_of_flow"] = False
    else:
        normalised["out_of_flow"] = False

    # --- style & layout validation ------------------------------------
    if "style" in elem:
        _validate_style_dict(elem["style"], path=f"{path}.style")
    if "layout" in elem:
        _validate_layout_dict(elem["layout"], path=f"{path}.layout")
    if "padding" in elem:
        pad = elem["padding"]
        if isinstance(pad, dict):
            for side in ("left", "right", "top", "bottom"):
                if side in pad:
                    val = pad[side]
                    if not isinstance(val, (int, float)) or val < 0:
                        raise SpecError(f"padding.{side} must be non-negative, got {val!r}.", path=f"{path}.padding.{side}")
        elif isinstance(pad, (int, float)):
            if pad < 0:
                raise SpecError(f"padding must be non-negative, got {pad!r}.", path=f"{path}.padding")
        elif pad is not None:
            raise SpecError("padding must be a number or a dictionary.", path=f"{path}.padding")

    # Preserve any extra user-supplied keys the renderer might use
    _KNOWN_KEYS = {"id", "type", "children", "footer", "out_of_flow", *_ELEMENT_DEFAULTS}
    for key in elem:
        if key not in _KNOWN_KEYS:
            normalised[key] = elem[key]

    # --- Collect result list (this element + flattened children) -------
    results: List[Dict[str, Any]] = [normalised]

    # --- children -----------------------------------------------------
    children_raw: Optional[list] = elem.get("children")
    if children_raw is not None:
        _require_type(children_raw, list, path=f"{path}.children", label="children")
        for idx, child in enumerate(children_raw):
            child_path = f"{path}.children[{idx}]"
            results.extend(
                _normalise_element(
                    child,
                    path=child_path,
                    existing_ids=existing_ids,
                    parent_id=elem_id,
                    parent_type=elem_type,
                )
            )

    # --- footer (panel-specific shorthand for a child element) --------
    footer_raw: Optional[dict] = elem.get("footer")
    if footer_raw is not None:
        if elem_type != "panel":
            raise SpecError(
                f"'footer' is only valid on 'panel' elements, but '{elem_id}' "
                f"has type '{elem_type}'.",
                path=f"{path}.footer",
            )
        _require_type(footer_raw, dict, path=f"{path}.footer", label="footer")

        # Synthesise an element dict for the footer if it doesn't have
        # an explicit type / id.
        footer_elem: Dict[str, Any] = dict(footer_raw)
        if "type" not in footer_elem:
            footer_elem["type"] = "label"
        if "id" not in footer_elem:
            footer_elem["id"] = _gen_id(f"{elem_id}_footer", existing_ids)
        # Mark it so the compiler can recognise its role
        footer_elem.setdefault("_role", "footer")

        results.extend(
            _normalise_element(
                footer_elem,
                path=f"{path}.footer",
                existing_ids=existing_ids,
                parent_id=elem_id,
                parent_type=elem_type,
            )
        )

    return results


def _normalise_elements(
    raw: list,
    *,
    path: str = "elements",
) -> List[Dict[str, Any]]:
    """Validate and normalise the full ``elements`` list.

    Nested ``children`` and ``footer`` entries are flattened into the
    returned list with ``parent`` back-references.

    Args:
        raw:  The raw ``elements`` list from the spec.
        path: JSONPath breadcrumb prefix.

    Returns:
        Flat list of normalised element dicts.

    Raises:
        SpecError: On any element-level validation failure.
    """
    _require_type(raw, list, path=path, label="elements")

    if len(raw) == 0:
        raise SpecError("'elements' must contain at least one element.", path=path)

    existing_ids: Set[str] = set()
    flat: List[Dict[str, Any]] = []

    for idx, elem in enumerate(raw):
        flat.extend(
            _normalise_element(
                elem,
                path=f"{path}[{idx}]",
                existing_ids=existing_ids,
            )
        )

    return flat


# ──────────────────────────────────────────────────────────────────────
# Connections
# ──────────────────────────────────────────────────────────────────────

def _normalise_connection(
    conn: dict,
    *,
    path: str,
    element_ids: Set[str],
) -> Dict[str, Any]:
    """Validate and normalise a single connection dict.

    Args:
        conn:        Raw connection dict.
        path:        JSONPath breadcrumb for errors.
        element_ids: Set of all known element IDs (for endpoint checks).

    Returns:
        Normalised connection dict.

    Raises:
        SpecError: On missing endpoints or unknown element references.
    """
    _require_type(conn, dict, path=path, label="connection")

    # --- required endpoints -------------------------------------------
    from_id: str = _require(conn, "from", path=path, expected="element ID string")
    to_id: str = _require(conn, "to", path=path, expected="element ID string")

    _require_type(from_id, str, path=f"{path}.from", label="from")
    _require_type(to_id, str, path=f"{path}.to", label="to")

    if from_id not in element_ids:
        raise SpecError(
            f"Connection 'from' references unknown element '{from_id}'.",
            path=f"{path}.from",
        )
    if to_id not in element_ids:
        raise SpecError(
            f"Connection 'to' references unknown element '{to_id}'.",
            path=f"{path}.to",
        )

    normalised: Dict[str, Any] = {"from": from_id, "to": to_id}

    # --- optional ports & aliases -------------------------------------
    exit_port_key = "exitPort" if conn.get("exitPort") is not None else ("fromPort" if conn.get("fromPort") is not None else None)
    if exit_port_key is not None:
        exit_port_val = conn[exit_port_key]
        _require_type(exit_port_val, str, path=f"{path}.{exit_port_key}", label=exit_port_key)
        _one_of(
            exit_port_val,
            SUPPORTED_PORTS,
            path=f"{path}.{exit_port_key}",
            label=exit_port_key,
        )
        normalised["exitPort"] = exit_port_val

    # Resolve entry port
    entry_port_key = "entryPort" if conn.get("entryPort") is not None else ("toPort" if conn.get("toPort") is not None else None)
    if entry_port_key is not None:
        entry_port_val = conn[entry_port_key]
        _require_type(entry_port_val, str, path=f"{path}.{entry_port_key}", label=entry_port_key)
        _one_of(
            entry_port_val,
            SUPPORTED_PORTS,
            path=f"{path}.{entry_port_key}",
            label=entry_port_key,
        )
        normalised["entryPort"] = entry_port_val

    # --- optional label -----------------------------------------------
    label: Optional[str] = conn.get("label")
    if label is not None:
        _require_type(label, str, path=f"{path}.label", label="label")
    normalised["label"] = label

    # --- optional style -----------------------------------------------
    style: Optional[str] = conn.get("style")
    if style is not None:
        _require_type(style, str, path=f"{path}.style", label="style")
        _one_of(style, SUPPORTED_CONNECTION_STYLES, path=f"{path}.style", label="style")
    normalised["style"] = style or "solid"

    # --- optional color -----------------------------------------------
    color: Optional[str] = conn.get("color")
    if color is not None:
        _require_type(color, str, path=f"{path}.color", label="color")
    normalised["color"] = color

    return normalised


def _normalise_connections(
    raw: Optional[list],
    *,
    element_ids: Set[str],
    path: str = "connections",
) -> List[Dict[str, Any]]:
    """Validate and normalise the ``connections`` list.

    Args:
        raw:         The raw ``connections`` list (may be ``None``).
        element_ids: Set of all known element IDs.
        path:        JSONPath breadcrumb prefix.

    Returns:
        List of normalised connection dicts (empty list if *raw* is ``None``).
    """
    if raw is None:
        return []

    _require_type(raw, list, path=path, label="connections")

    return [
        _normalise_connection(conn, path=f"{path}[{idx}]", element_ids=element_ids)
        for idx, conn in enumerate(raw)
    ]


# ──────────────────────────────────────────────────────────────────────
# Annotations
# ──────────────────────────────────────────────────────────────────────

def _normalise_annotation(
    ann: dict,
    *,
    path: str,
    element_ids: Set[str],
    connection_keys: Set[tuple[str, str]],
) -> Dict[str, Any]:
    """Validate and normalise a single annotation dict.

    An annotation may attach to an element (``attachTo``) **or** to a
    connection midpoint (``from`` + ``to``).  At least one attachment
    mode must be specified.

    Args:
        ann:             Raw annotation dict.
        path:            JSONPath breadcrumb.
        element_ids:     Set of all known element IDs.
        connection_keys: Set of ``(from_id, to_id)`` tuples for all
                         normalised connections (for midpoint validation).

    Returns:
        Normalised annotation dict.

    Raises:
        SpecError: On missing ``text``, invalid attachment, or unknown refs.
    """
    _require_type(ann, dict, path=path, label="annotation")

    # --- text (required) ----------------------------------------------
    text: str = _require(ann, "text", path=path, expected="annotation text string")
    _require_type(text, str, path=f"{path}.text", label="text")

    normalised: Dict[str, Any] = {"text": text}

    # --- attachment mode ----------------------------------------------
    attach_to: Optional[str] = ann.get("attachTo")
    ann_from: Optional[str] = ann.get("from")
    ann_to: Optional[str] = ann.get("to")

    if attach_to is not None:
        # Attach to an element
        _require_type(attach_to, str, path=f"{path}.attachTo", label="attachTo")
        if attach_to not in element_ids:
            raise SpecError(
                f"Annotation 'attachTo' references unknown element '{attach_to}'.",
                path=f"{path}.attachTo",
            )
        normalised["attachTo"] = attach_to

    elif ann_from is not None and ann_to is not None:
        # Attach to a connection midpoint
        _require_type(ann_from, str, path=f"{path}.from", label="from")
        _require_type(ann_to, str, path=f"{path}.to", label="to")

        if ann_from not in element_ids:
            raise SpecError(
                f"Annotation 'from' references unknown element '{ann_from}'.",
                path=f"{path}.from",
            )
        if ann_to not in element_ids:
            raise SpecError(
                f"Annotation 'to' references unknown element '{ann_to}'.",
                path=f"{path}.to",
            )

        key = (ann_from, ann_to)
        if key not in connection_keys:
            raise SpecError(
                f"Annotation references a connection from '{ann_from}' to "
                f"'{ann_to}' that does not exist.",
                path=path,
            )
        normalised["from"] = ann_from
        normalised["to"] = ann_to

    else:
        raise SpecError(
            "Annotation must specify either 'attachTo' (element ID) or both "
            "'from' and 'to' (connection midpoint).",
            path=path,
        )

    # --- optional position --------------------------------------------
    position: Optional[str] = ann.get("position")
    if position is not None:
        _require_type(position, str, path=f"{path}.position", label="position")
        _one_of(
            position,
            SUPPORTED_ANNOTATION_POSITIONS,
            path=f"{path}.position",
            label="position",
        )
    normalised["position"] = position or "top"

    return normalised


def _normalise_annotations(
    raw: Optional[list],
    *,
    element_ids: Set[str],
    connections: List[Dict[str, Any]],
    path: str = "annotations",
) -> List[Dict[str, Any]]:
    """Validate and normalise the ``annotations`` list.

    Args:
        raw:         The raw ``annotations`` list (may be ``None``).
        element_ids: Set of all known element IDs.
        connections: Already-normalised connections (for midpoint lookups).
        path:        JSONPath breadcrumb prefix.

    Returns:
        List of normalised annotation dicts (empty list if *raw* is ``None``).
    """
    if raw is None:
        return []

    _require_type(raw, list, path=path, label="annotations")

    # Build a lookup set for connection endpoints
    connection_keys: Set[tuple[str, str]] = {
        (c["from"], c["to"]) for c in connections
    }

    return [
        _normalise_annotation(
            ann,
            path=f"{path}[{idx}]",
            element_ids=element_ids,
            connection_keys=connection_keys,
        )
        for idx, ann in enumerate(raw)
    ]


def _normalise_decision_branches(elements: list[dict], connections: list[dict]) -> None:
    decision_ids = {e["id"] for e in elements if e.get("type") == "diamond"}
    for d_id in decision_ids:
        outgoing = [
            c for c in connections 
            if c.get("from") == d_id or (isinstance(c.get("path"), list) and len(c.get("path")) > 0 and c.get("path")[0] == d_id)
        ]
        if len(outgoing) > 1:
            default_labels = ["Yes", "No", "Branch 3", "Branch 4"]
            for idx, conn in enumerate(outgoing):
                if not conn.get("label"):
                    conn["label"] = default_labels[idx] if idx < len(default_labels) else f"Branch {idx+1}"


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def validate_spec(spec: dict) -> dict:
    """Validate and normalise a FlowDraft v2 spec.

    This is the **single entry point** for spec ingestion.  Call it once
    on the raw JSON dict loaded from disk and pass the returned dict to
    the compiler.

    Processing order:

    1. Deep-copy the input so the original is never mutated.
    2. Validate / default top-level keys (``canvas``, ``theme``).
    3. Normalise ``elements`` — flatten children, assign parents.
    4. Normalise ``connections`` — validate endpoints.
    5. Normalise ``annotations`` — validate attachment targets.

    Args:
        spec: Raw JSON dict (as loaded by ``json.load``).

    Returns:
        A fully normalised spec dict ready for the compiler.

    Raises:
        SpecError: If any validation check fails.

    Example::

        import json
        from flowdraft.schema import validate_spec, SpecError

        with open("my-diagram.json") as f:
            raw = json.load(f)

        try:
            spec = validate_spec(raw)
        except SpecError as exc:
            print(f"Invalid spec at {exc.path}: {exc.reason}")
    """
    if not isinstance(spec, dict):
        raise SpecError(
            f"Spec must be a JSON object (dict), got {type(spec).__name__}.",
            path="<root>",
        )

    # Work on a deep copy so we never mutate the caller's dict
    spec = copy.deepcopy(spec)

    result: Dict[str, Any] = {}

    # ── canvas ────────────────────────────────────────────────────────
    result["canvas"] = _normalise_canvas(spec.get("canvas"), path="canvas")

    # ── theme ─────────────────────────────────────────────────────────
    theme = spec.get("theme", "dark")
    if isinstance(theme, dict):
        result["theme"] = theme
    else:
        _require_type(theme, str, path="theme", label="theme")
        _one_of(theme, SUPPORTED_THEMES, path="theme", label="theme")
        result["theme"] = theme

    # ── Validate top-level style / layout ─────────────────────────────
    if "style" in spec:
        _validate_style_dict(spec["style"], path="style")
    if "layout" in spec:
        _validate_layout_dict(spec["layout"], path="layout")

    # ── elements (required) ───────────────────────────────────────────
    _require(spec, "elements", path="<root>", expected="list of element dicts")
    elements = _normalise_elements(spec["elements"], path="elements")
    result["elements"] = elements

    # Build the full set of element IDs for cross-reference validation
    element_ids: Set[str] = {e["id"] for e in elements}

    # ── connections (optional) ────────────────────────────────────────
    connections = _normalise_connections(
        spec.get("connections"),
        element_ids=element_ids,
        path="connections",
    )
    _normalise_decision_branches(elements, connections)
    result["connections"] = connections

    # ── annotations (optional) ────────────────────────────────────────
    annotations = _normalise_annotations(
        spec.get("annotations"),
        element_ids=element_ids,
        connections=connections,
        path="annotations",
    )
    result["annotations"] = annotations

    # ── pass-through keys ─────────────────────────────────────────────
    # Preserve well-known optional top-level keys that downstream code
    # may inspect (e.g. ``auto_layout``, ``hand``, ``signature``,
    # ``title``).
    _TOP_LEVEL_MANAGED = {"canvas", "theme", "elements", "connections", "annotations"}
    for key, value in spec.items():
        if key not in _TOP_LEVEL_MANAGED:
            result[key] = value

    return result
