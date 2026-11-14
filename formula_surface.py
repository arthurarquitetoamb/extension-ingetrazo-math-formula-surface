# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 IngeTrazo contributors.
"""Formula Surface — build a 3D surface from z = f(x, y) written in Python.

The plugin adds a side panel (and an entry in Extensions) with:

* an open formula field: ``z = f(x, y)``, using Python syntax;
* an X interval and a Y interval, plus the number of divisions;
* a list of ready-made examples with the name of the shape each one makes;
* a Z scale, for formulas whose numbers are not in metres.

Pressing **Build surface** turns the formula into ONE IngeTrazo group of
quad faces over the grid, selected and with its own undo step. Invalid grid
points (division by zero, square root of a negative number, complex or
non-finite results) are skipped instead of aborting the whole surface.

Install: copy this file to ``%APPDATA%\\IngeTrazo\\plugins`` (Windows),
``$XDG_DATA_HOME/ingetrazo/plugins`` (Linux) or the equivalent per-user
folder, and restart IngeTrazo. It appears under Extensions → Formula
Surface and as a tab in the side tray.

The expression is evaluated with Python's ``eval`` in a small namespace
(``x``, ``y``, the ``math`` module and common math names). Only math is
exposed, but this is still local Python: do not paste formulas from people
you do not trust.
"""
from __future__ import annotations

import html
import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QFontDatabase,
    QKeySequence,
    QShortcut,
    QVector3D,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.group import Group
from core.history import Command
from core.mesh import Mesh

log = logging.getLogger("ingetrazo.plugins.formula_surface")

#: Document-data key. The file name is the natural stable key for a loose
#: plugin (the same convention ExtensionApp.key uses).
KEY = Path(__file__).stem

#: Number of grid cells a surface may have, at most, in each direction.
MAX_DIVISIONS = 160

#: Interior creases below this angle (between neighbouring faces) shade
#: smooth; sharper folds (a pyramid's ridges, a cone's rim) stay crisp.
SMOOTH_ANGLE_DEG = 40.0


# ---------------------------------------------------------------------------
# Examples: the name of the shape and the Python formula that makes it
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Example:
    shape: str
    formula: str
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    divisions_x: int = 48
    divisions_y: int = 48
    math_formula: str = ""


EXAMPLES: tuple[Example, ...] = (
    Example("Elliptic paraboloid (bowl)", "x**2 + y**2",
            -2, 2, -2, 2, 48, 48,
            "z = x² + y²"),
    Example("Stretched elliptic paraboloid", "x**2/4 + y**2/9",
            -3, 3, -4, 4, 48, 56,
            "z = x²/4 + y²/9"),
    Example("Hyperbolic paraboloid (saddle)", "x**2 - y**2",
            -2, 2, -2, 2, 48, 48,
            "z = x² − y²"),
    Example("Hyperbolic paraboloid (rotated)", "x*y",
            -2, 2, -2, 2, 48, 48,
            "z = x·y"),
    Example("Inclined plane", "x + y",
            -2, 2, -2, 2, 24, 24,
            "z = x + y"),
    Example("Hemisphere (radius 3)", "sqrt(9 - x**2 - y**2)",
            -3, 3, -3, 3, 72, 72,
            "z = √(9 − x² − y²)"),
    Example("Ellipsoidal dome", "sqrt(1 - x**2/9 - y**2/16)",
            -3, 3, -4, 4, 72, 72,
            "z = √(1 − x²/9 − y²/16)"),
    Example("Cone (upper nappe)", "sqrt(x**2 + y**2)",
            -2, 2, -2, 2, 64, 64,
            "z = √(x² + y²)"),
    Example("Square pyramid", "max(abs(x), abs(y))",
            -2, 2, -2, 2, 48, 48,
            "z = max(|x|, |y|)"),
    Example("Diamond pyramid", "abs(x) + abs(y)",
            -2, 2, -2, 2, 48, 48,
            "z = |x| + |y|"),
    Example("Gaussian bell", "exp(-(x**2 + y**2))",
            -3, 3, -3, 3, 64, 64,
            "z = e^(−(x² + y²))"),
    Example("Lorentzian hill", "1/(1 + x**2 + y**2)",
            -4, 4, -4, 4, 56, 56,
            "z = 1/(1 + x² + y²)"),
    Example("Egg-crate surface", "sin(x)*cos(y)",
            -math.pi, math.pi, -math.pi, math.pi, 64, 64,
            "z = sin(x)·cos(y)"),
    Example("Concentric ripples", "sin(sqrt(x**2 + y**2))",
            -10, 10, -10, 10, 80, 80,
            "z = sin(√(x² + y²))"),
    Example("Sombrero (Mexican hat)",
            "sin(sqrt(x**2 + y**2))/(sqrt(x**2 + y**2) + 1e-9)",
            -10, 10, -10, 10, 96, 96,
            "z = sin(√(x² + y²)) / (√(x² + y²) + ε)"),
    Example("Monkey saddle", "x**3 - 3*x*y**2",
            -2, 2, -2, 2, 72, 72,
            "z = x³ − 3xy²"),
    Example("Logarithmic bowl", "log(x**2 + y**2 + 1)",
            -3, 3, -3, 3, 64, 64,
            "z = ln(x² + y² + 1)"),
    Example("Twisted wave", "sin(x*y)",
            -3, 3, -3, 3, 64, 64,
            "z = sin(x·y)"),
    Example("Damped radial waves",
            "exp(-(x**2 + y**2)/20)*sin(2*sqrt(x**2 + y**2))",
            -10, 10, -10, 10, 80, 80,
            "z = e^(−(x² + y²)/20)·sin(2√(x² + y²))"),
    Example("Damped egg-crate",
            "sin(3*x)*cos(3*y)*exp(-(x**2 + y**2)/20)",
            -5, 5, -5, 5, 72, 72,
            "z = sin(3x)·cos(3y)·e^(−(x² + y²)/20)"),
    Example("Wavy sheet", "sin(x) + sin(y)",
            -math.pi, math.pi, -math.pi, math.pi, 64, 64,
            "z = sin(x) + sin(y)"),
)


# ---------------------------------------------------------------------------
# Formula evaluation
# ---------------------------------------------------------------------------

class FormulaError(Exception):
    """A problem the user can fix: bad expression, bad range, no surface."""


_PREFIX = re.compile(
    r"^\s*(?:z|f\s*\(\s*x\s*,\s*y\s*\)|z\s*\(\s*x\s*,\s*y\s*\))\s*=\s*",
    re.IGNORECASE)


def _math_namespace() -> dict:
    """The names a formula may use, without Python's builtins."""
    names = {name: getattr(math, name) for name in dir(math)
             if not name.startswith("_")}
    names.update({
        "abs": abs, "min": min, "max": max, "round": round,
        "pow": pow, "float": float, "int": int, "bool": bool,
    })
    names["math"] = math
    names["__builtins__"] = {}
    return names


FORMULA_NAMESPACE = _math_namespace()


def compile_formula(text: str):
    """Return ``(clean_text, code)`` for the user's formula.

    ``z = ...``, ``f(x, y) = ...`` and ``z(x, y) = ...`` prefixes are
    accepted; the rest must be ONE Python expression in x and y.
    """
    text = (text or "").strip()
    if not text:
        raise FormulaError("Write a formula in x and y, for example x**2 + y**2.")
    text = _PREFIX.sub("", text).strip()
    if not text:
        raise FormulaError("The formula is empty after the equals sign.")
    if "^" in text:
        raise FormulaError(
            "Use ** for powers, not ^ — for example x**2 + y**2.")
    try:
        code = compile(text, "<formula>", "eval")
    except SyntaxError as exc:
        detail = (exc.msg or "invalid syntax").strip()
        where = f" (line {exc.lineno})" if exc.lineno else ""
        raise FormulaError(
            f"Invalid Python expression: {detail}{where}.") from None
    return text, code


def _friendly_error(exc: BaseException) -> str:
    if isinstance(exc, ZeroDivisionError):
        return "division by zero"
    if isinstance(exc, OverflowError):
        return "number too large"
    if isinstance(exc, ValueError):
        return str(exc).strip() or "math domain error"
    if isinstance(exc, NameError):
        name = getattr(exc, "name", None)
        return f"unknown name {name!r}" if name else "unknown name"
    if isinstance(exc, TypeError):
        return str(exc).strip() or "wrong type"
    return f"{type(exc).__name__}: {exc}"


@dataclass
class SurfaceResult:
    group: Group
    grid_points: int
    valid_points: int
    skipped_points: int
    faces: int
    first_problem: str | None


def _surface_name(expression: str) -> str:
    base = f"Surface: z = {expression}"
    return base if len(base) <= 72 else base[:69].rstrip() + "..."


def _smooth_curved_edges(mesh: Mesh) -> None:
    """Soften the seams between nearly coplanar facets, so the surface shades
    smooth. Sharp folds and the outer border keep their lines."""
    limit = math.cos(math.radians(SMOOTH_ANGLE_DEG))
    for edge in mesh.edges:
        if len(edge.faces) != 2:
            continue
        f0, f1 = edge.faces[0], edge.faces[1]
        if f0 is f1:
            continue
        if QVector3D.dotProduct(f0.normal(), f1.normal()) >= limit:
            edge.soft = True


def build_surface_group(
    formula: str,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
    divisions_x: int = 48,
    divisions_y: int = 48,
    *,
    z_scale: float = 1.0,
    smooth: bool = True,
    name: str | None = None,
    layer: str | None = None,
    shape_name: str | None = None,
) -> SurfaceResult:
    """Build one Group with the graph of ``z = f(x, y)`` over the rectangle.

    The mesh is a grid of quads with the formula sampled at their corners.
    Points where the formula raises or gives a non-finite/complex value are
    left out, which also lets a surface stop at the edge of its natural
    domain (a hemisphere inside a square X/Y range, for instance).
    """
    try:
        x_min, x_max = float(x_min), float(x_max)
        y_min, y_max = float(y_min), float(y_max)
    except (TypeError, ValueError):
        raise FormulaError("The X and Y ranges must be numbers.") from None
    if not (math.isfinite(x_min) and math.isfinite(x_max)
            and math.isfinite(y_min) and math.isfinite(y_max)):
        raise FormulaError("The X and Y ranges must be finite numbers.")
    if x_min >= x_max or y_min >= y_max:
        raise FormulaError("Each range needs a minimum smaller than its maximum.")
    nx, ny = int(divisions_x), int(divisions_y)
    if nx < 2 or ny < 2:
        raise FormulaError("Use at least 2 divisions in each direction.")
    if nx > MAX_DIVISIONS or ny > MAX_DIVISIONS:
        raise FormulaError(f"Use at most {MAX_DIVISIONS} divisions in each direction.")
    z_scale = float(z_scale)
    if not math.isfinite(z_scale):
        raise FormulaError("The Z scale must be a finite number.")

    expression, code = compile_formula(formula)

    xs = [x_min + (x_max - x_min) * i / nx for i in range(nx + 1)]
    ys = [y_min + (y_max - y_min) * j / ny for j in range(ny + 1)]
    positions: list[list[QVector3D | None]] = []
    skipped = 0
    first_problem = None

    for y in ys:
        row: list[QVector3D | None] = []
        for x in xs:
            try:
                value = eval(code, FORMULA_NAMESPACE, {"x": x, "y": y})
                if isinstance(value, complex):
                    if abs(value.imag) > 1e-12:
                        raise ValueError("complex result")
                    value = value.real
                z = float(value) * z_scale
                if not math.isfinite(z):
                    raise ValueError("not a finite number")
                row.append(QVector3D(x, y, z))
            except Exception as exc:  # noqa: BLE001 — one bad point is skipped
                row.append(None)
                skipped += 1
                if first_problem is None:
                    first_problem = _friendly_error(exc)
        positions.append(row)

    total_points = (nx + 1) * (ny + 1)
    if skipped == total_points:
        reason = f" ({first_problem})" if first_problem else ""
        raise FormulaError(
            f"No grid point produced a valid number{reason}. "
            "Check the formula and the X/Y ranges.")

    mesh = Mesh()
    vertices: list[list] = []
    for row in positions:
        vertices.append([mesh.vertex(p) if p is not None else None
                         for p in row])

    faces = 0
    for j in range(ny):
        for i in range(nx):
            corners = (vertices[j][i], vertices[j][i + 1],
                       vertices[j + 1][i + 1], vertices[j + 1][i])
            if any(v is None for v in corners):
                continue
            mesh.add_face([v.position for v in corners])
            faces += 1

    if faces == 0:
        raise FormulaError(
            "No complete grid cell had four valid corners. "
            "Increase the divisions or widen the ranges.")

    if smooth:
        _smooth_curved_edges(mesh)

    group = Group(mesh, name=name or _surface_name(expression))
    group.layer = layer
    group.ext = {
        KEY: {
            "formula": expression,
            "shape": shape_name,
            "x_min": x_min, "x_max": x_max,
            "y_min": y_min, "y_max": y_max,
            "divisions_x": nx, "divisions_y": ny,
            "z_scale": z_scale,
            "smooth": bool(smooth),
            "version": 1,
        }
    }
    return SurfaceResult(
        group=group,
        grid_points=total_points,
        valid_points=total_points - skipped,
        skipped_points=skipped,
        faces=faces,
        first_problem=first_problem,
    )


# ---------------------------------------------------------------------------
# One undo step: add (or remove) the finished surface group
# ---------------------------------------------------------------------------

class AddSurfaceCommand(Command):
    """Put a finished surface in the model and select it, as one undo step."""

    keeps_groups = True

    def __init__(self, group: Group) -> None:
        self.group = group
        self._before_selection: set | None = None
        self._added = False

    def do(self, scene) -> None:
        if self._before_selection is None:
            try:
                self._before_selection = set(scene.selection)
            except Exception:
                self._before_selection = set()
        if self.group not in scene.groups:
            scene.groups.append(self.group)
            self._added = True
        try:
            scene.selection.clear()
            scene.selection.add(self.group)
        except Exception:
            pass
        scene.version = getattr(scene, "version", 0) + 1

    def undo(self, scene) -> None:
        if self.group in scene.groups:
            try:
                scene.groups.remove(self.group)
            except ValueError:
                pass
        try:
            scene.selection.clear()
            if self._before_selection:
                scene.selection.update(self._before_selection)
        except Exception:
            pass
        scene.version = getattr(scene, "version", 0) + 1


def _unique_name(base: str, names) -> str:
    taken = {name for name in names if name}
    if base not in taken:
        return base
    k = 2
    while f"{base} #{k}" in taken:
        k += 1
    return f"{base} #{k}"


# ---------------------------------------------------------------------------
# The side panel
# ---------------------------------------------------------------------------

class FormulaSurfacePanel(QWidget):
    """The panel: formula field, X/Y ranges, examples and Build button."""

    def __init__(self, app, parent=None) -> None:
        super().__init__(parent)
        self._app = app
        self._loading_example = False
        self._build_ui()
        self._load_example(0, select=True)

    # ---- Widgets ---------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        title = QLabel("<b>Surface from a formula</b>")
        root.addWidget(title)

        intro = QLabel(
            "Build the graph of <b>z = f(x, y)</b> over an X interval and a "
            "Y interval. The result is one group of quad faces, selected and "
            "undoable with a single Ctrl+Z.")
        intro.setWordWrap(True)
        root.addWidget(intro)

        # Formula ----------------------------------------------------------
        formula_box = QGroupBox("Formula")
        formula_layout = QVBoxLayout(formula_box)
        formula_layout.setContentsMargins(6, 6, 6, 6)
        formula_layout.setSpacing(4)

        self._formula = QPlainTextEdit()
        self._formula.setPlaceholderText("x**2 + y**2")
        self._formula.setToolTip(
            "A Python expression in x and y. Use ** for powers.\n"
            "Examples: x**2 + y**2, sin(x)*cos(y), sqrt(9 - x**2 - y**2).")
        self._formula.setTabChangesFocus(True)
        self._formula.setMaximumHeight(84)
        mono = QFontDatabase.systemFont(QFontDatabase.FixedFont)
        mono.setPointSize(10)
        self._formula.setFont(mono)
        formula_layout.addWidget(self._formula)

        hint = QLabel(
            "Use <b>x</b> and <b>y</b>; <b>**</b> is the power operator. "
            "Available: sin, cos, tan, sqrt, exp, log, abs, min, max, pi, e, "
            "tau and the <b>math</b> module. Invalid points are skipped.")
        hint.setWordWrap(True)
        formula_layout.addWidget(hint)
        root.addWidget(formula_box)

        # Domain and resolution -------------------------------------------
        domain_box = QGroupBox("Domain and resolution")
        form = QFormLayout(domain_box)
        form.setContentsMargins(6, 6, 6, 6)
        form.setSpacing(4)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)

        self._x_min = self._double_spin(-2.0)
        self._x_max = self._double_spin(2.0)
        self._y_min = self._double_spin(-2.0)
        self._y_max = self._double_spin(2.0)
        form.addRow("X range", self._pair_row(self._x_min, "to", self._x_max))
        form.addRow("Y range", self._pair_row(self._y_min, "to", self._y_max))

        self._div_x = QSpinBox()
        self._div_y = QSpinBox()
        for spin in (self._div_x, self._div_y):
            spin.setRange(2, MAX_DIVISIONS)
            spin.setKeyboardTracking(False)
        self._div_x.setValue(48)
        self._div_y.setValue(48)
        form.addRow("Divisions X", self._div_x)
        form.addRow("Divisions Y", self._div_y)

        self._z_scale = QDoubleSpinBox()
        self._z_scale.setDecimals(3)
        self._z_scale.setRange(0.001, 1000.0)
        self._z_scale.setSingleStep(0.1)
        self._z_scale.setValue(1.0)
        self._z_scale.setKeyboardTracking(False)
        self._z_scale.setToolTip(
            "Multiplies the formula's z values, so a surface whose numbers "
            "are not in metres can be sized in the model.")
        form.addRow("Z scale", self._z_scale)

        self._smooth = QCheckBox("Smooth shading on curved parts")
        self._smooth.setChecked(True)
        form.addRow("", self._smooth)
        root.addWidget(domain_box)

        # Examples ---------------------------------------------------------
        examples_box = QGroupBox("Examples")
        examples_layout = QVBoxLayout(examples_box)
        examples_layout.setContentsMargins(6, 6, 6, 6)
        examples_layout.setSpacing(4)

        self._examples = QComboBox()
        self._examples.setSizeAdjustPolicy(
            QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self._examples.setMinimumContentsLength(24)
        self._examples.addItem("Custom expression", -1)
        for index, example in enumerate(EXAMPLES):
            common = f" ({example.math_formula})" if example.math_formula else ""
            text = f"{example.shape}  —  z = {example.formula}{common}"
            self._examples.addItem(text, index)
            self._examples.setItemData(index + 1, text, Qt.ToolTipRole)
        self._examples.currentIndexChanged.connect(self._on_example_changed)
        examples_layout.addWidget(self._examples)

        self._example_info = QLabel()
        self._example_info.setWordWrap(True)
        self._example_info.setTextInteractionFlags(Qt.TextSelectableByMouse)
        examples_layout.addWidget(self._example_info)
        root.addWidget(examples_box)

        # Buttons and status ----------------------------------------------
        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        self._build_button = QPushButton("Build surface")
        self._build_button.setToolTip(
            "Create the surface as one group (Ctrl+Enter).")
        self._build_button.clicked.connect(self._on_build)
        buttons.addWidget(self._build_button, 1)
        reset = QPushButton("Reset")
        reset.setToolTip("Load the paraboloid example again.")
        reset.clicked.connect(lambda: self._load_example(0, select=True))
        buttons.addWidget(reset)
        root.addLayout(buttons)

        self._status = QLabel("Ready.")
        self._status.setWordWrap(True)
        root.addWidget(self._status)
        root.addStretch(1)

        self._formula.textChanged.connect(self._on_formula_changed)

        shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        shortcut.setContext(Qt.WidgetWithChildrenShortcut)
        shortcut.activated.connect(self._on_build)

    @staticmethod
    def _double_spin(value: float) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(3)
        spin.setRange(-1_000_000.0, 1_000_000.0)
        spin.setSingleStep(0.1)
        spin.setValue(value)
        spin.setKeyboardTracking(False)
        spin.setMinimumWidth(60)
        return spin

    @staticmethod
    def _pair_row(left: QWidget, label: str, right: QWidget) -> QWidget:
        holder = QWidget()
        row = QHBoxLayout(holder)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(4)
        row.addWidget(left, 1)
        row.addWidget(QLabel(label))
        row.addWidget(right, 1)
        return holder

    # ---- Examples --------------------------------------------------------
    def _on_example_changed(self, index: int) -> None:
        data = self._examples.itemData(index)
        if data is None or int(data) < 0:
            self._example_info.setText(
                "Custom expression — write any Python formula in x and y.")
            return
        self._load_example(int(data), select=False)

    def _load_example(self, index: int, *, select: bool) -> None:
        example = EXAMPLES[index]
        self._loading_example = True
        try:
            self._formula.setPlainText(example.formula)
            self._x_min.setValue(example.x_min)
            self._x_max.setValue(example.x_max)
            self._y_min.setValue(example.y_min)
            self._y_max.setValue(example.y_max)
            self._div_x.setValue(example.divisions_x)
            self._div_y.setValue(example.divisions_y)
            self._z_scale.setValue(1.0)
            self._smooth.setChecked(True)
            if select:
                self._examples.blockSignals(True)
                self._examples.setCurrentIndex(index + 1)
                self._examples.blockSignals(False)
        finally:
            self._loading_example = False
        common = f" &nbsp; <span>({html.escape(example.math_formula)})</span>" if example.math_formula else ""
        self._example_info.setText(
            f"<b>{html.escape(example.shape)}</b><br>"
            f"<code>z = {html.escape(example.formula)}</code>{common}")
        self._set_status("Example loaded. Press Build surface.")

    def _on_formula_changed(self) -> None:
        if self._loading_example:
            return
        if self._examples.currentIndex() != 0:
            self._examples.blockSignals(True)
            self._examples.setCurrentIndex(0)
            self._examples.blockSignals(False)
        self._example_info.setText(
            "Custom expression — write any Python formula in x and y.")

    # ---- Build -----------------------------------------------------------
    def _set_status(self, text: str, *, error: bool = False) -> None:
        self._status.setText(text)
        self._status.setStyleSheet("color: #c0392b;" if error else "")

    def _current_shape_name(self) -> str | None:
        data = self._examples.currentData()
        if data is None or int(data) < 0:
            return None
        return EXAMPLES[int(data)].shape

    def _on_build(self) -> None:
        viewport = getattr(self._app, "viewport", None)
        if viewport is None:
            self._set_status("No active viewport.", error=True)
            return
        scene = getattr(viewport, "scene", None)
        history = getattr(viewport, "history", None)
        if scene is None or history is None:
            self._set_status("The document is not ready yet.", error=True)
            return
        if getattr(scene, "edit_group", None) is not None:
            self._set_status(
                "Close the group you are editing, then build the surface.",
                error=True)
            return

        try:
            result = build_surface_group(
                self._formula.toPlainText(),
                self._x_min.value(), self._x_max.value(),
                self._y_min.value(), self._y_max.value(),
                self._div_x.value(), self._div_y.value(),
                z_scale=self._z_scale.value(),
                smooth=self._smooth.isChecked(),
                layer=getattr(scene, "active_layer", None),
                shape_name=self._current_shape_name(),
            )
        except FormulaError as exc:
            self._set_status(str(exc), error=True)
            return
        except Exception as exc:  # noqa: BLE001 — never break the panel
            log.exception("formula surface build failed")
            self._set_status(f"Could not build the surface: {exc}", error=True)
            return

        result.group.name = _unique_name(
            result.group.name, (getattr(g, "name", "") for g in getattr(scene, "groups", [])))

        cmd = AddSurfaceCommand(result.group)
        try:
            history.execute(cmd)
        except Exception as exc:  # noqa: BLE001
            log.exception("formula surface command failed")
            self._set_status(f"Could not add the surface: {exc}", error=True)
            return

        last_error = getattr(history, "last_error", None)
        last_rejected = getattr(history, "last_rejected", None)
        if last_error:
            if result.group in getattr(scene, "groups", []):
                try:
                    scene.groups.remove(result.group)
                except ValueError:
                    pass
            try:
                scene.selection.discard(result.group)
            except Exception:
                pass
            msg = str(last_error)
            self._set_status(
                "Could not add the surface: " + msg.split(": ", 1)[-1],
                error=True)
            return
        if last_rejected:
            self._set_status(f"Could not add the surface: {last_rejected}", error=True)
            return

        # Make sure the viewport reflects the new geometry immediately.
        for name in ("notify_scene_changed", "update_view", "rebuild",
                     "invalidate", "refresh"):
            fn = getattr(viewport, name, None)
            if callable(fn):
                try:
                    if name == "notify_scene_changed":
                        fn()
                    else:
                        fn()
                except TypeError:
                    try:
                        fn(True)
                    except Exception:
                        pass
                except Exception:
                    pass
        try:
            viewport.update()
        except Exception:
            pass
        try:
            viewport.setFocus()
        except Exception:
            pass

        message = (f"Built {result.faces:,} faces from "
                   f"{result.valid_points:,} valid grid points.")
        if result.skipped_points:
            message += (f" {result.skipped_points:,} point(s) skipped"
                        f" ({result.first_problem}).")
        self._set_status(message + " One undo step (Ctrl+Z).")
        flash = getattr(viewport, "flash_status", None)
        if callable(flash):
            try:
                flash(f"Formula surface: {result.faces:,} faces", 4000)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Extension entry point
# ---------------------------------------------------------------------------

def setup(app) -> None:
    """Add the panel and the Extensions-menu entry."""
    panel = FormulaSurfacePanel(app)
    # Stable, namespaced panel name so the dock can be restored/tabbed like
    # other extension panels instead of becoming a detached/duplicated one.
    dock = app.add_panel("Formula Surface", panel, name="panel")
    app.add_menu_action(
        "Formula Surface",
        lambda: app.show_panel(dock),
        tip="Build a 3D surface from z = f(x, y) written in Python.")
