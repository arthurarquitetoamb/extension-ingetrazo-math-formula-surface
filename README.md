# Formula Surface for IngeTrazo

Build 3D surfaces in [IngeTrazo](https://ingetrazo.com/) directly from mathematical formulas of the form **`z = f(x, y)`** written in Python syntax.

The plugin adds a side panel where you can enter a formula, define the X/Y domain and grid resolution, pick from ready-made examples, and generate a mesh surface as a single undoable group.

![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)
![Platform](https://img.shields.io/badge/platform-IngeTrazo%200.x-lightgrey)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB)

<img width="689" height="567" alt="Surfaces" src="https://github.com/user-attachments/assets/e9d866eb-0bcf-4439-b314-0ef000c77849" />


## Features

- **Formula-driven surfaces**: generate the graph of `z = f(x, y)` over a rectangular domain.
- **Python-style expressions**: use `x`, `y`, `**` for powers, and common math functions/constants (`sin`, `cos`, `tan`, `sqrt`, `exp`, `log`, `abs`, `min`, `max`, `pi`, `e`, `tau`, `math.*`, etc.).
- **Flexible input forms**: accepts plain expressions like `x**2 + y**2`, or prefixed forms such as `z = ...`, `f(x, y) = ...`, `z(x, y) = ...`.
- **Built-in examples**: includes a curated list of classic surfaces (paraboloids, saddle, plane, hemisphere, cone, pyramids, Gaussian bell, ripples, monkey saddle, and more) with preconfigured domains and resolutions.
- **Configurable domain and resolution**:
  - X and Y ranges
  - divisions in X/Y (grid density, up to 160 per direction)
  - Z scale (useful when formula values are not in meters)
- **Robust sampling**: invalid sample points (e.g. division by zero, domain errors, complex/non-finite values) are skipped instead of aborting the whole surface generation.
- **Smooth shading option**: can soften interior edges between nearly coplanar faces for smoother-looking curved surfaces while keeping sharp folds/crisp borders where appropriate.
- **Non-destructive editing workflow**:
  - creates **one group** of quad faces
  - selects the generated group
  - adds the operation as **one undo/redo step** (`Ctrl+Z`)
  - stores formula/domain metadata on the group (`group.ext`)
- **Convenient UI**:
  - side panel tab in IngeTrazo
  - **Extensions → Formula Surface** menu entry to show/focus the panel
  - `Ctrl+Enter` shortcut to build the surface from the panel

## How it works

The plugin samples the expression on a regular `(X, Y)` grid and creates quad faces from valid neighboring grid points.

- Valid sampled points become mesh vertices at `(x, y, z * z_scale)`.
- Grid cells with missing/invalid corners are skipped, so surfaces with limited domains (for example, a hemisphere sampled over a square range) can be generated naturally.
- If enabled, interior edges below a smooth-angle threshold are marked soft to improve shading on curved regions.

The result is a standard IngeTrazo group placed in the current scene/layer, so it can be selected, moved, transformed, and grouped with other objects using normal IngeTrazo tools.

## Requirements

- **IngeTrazo** 0.x with the Python extension API (`setup(app)`, `add_panel`, `add_menu_action`)
- **Python 3.9+**
- **PySide6** (bundled with IngeTrazo)
- IngeTrazo conventions: **Z-up**, units in **meters**, angles in **radians** (relevant for trig functions in formulas)

> Note: the IngeTrazo plugin API is still evolving in the 0.x series; future releases may require minor adjustments.

## Installation

1. Download/copy `formula_surface.py`.
2. Place it in your IngeTrazo user plugins folder:
   - **Windows:** `%APPDATA%\ingetrazo\plugins\`
   - **Linux:** `$XDG_DATA_HOME/ingetrazo/plugins/` (usually `~/.local/share/ingetrazo/plugins/`)
   - **macOS / other:** use the folder opened by **Extensions ▸ Open plugins folder** in IngeTrazo.
3. Restart IngeTrazo (plugins are discovered at startup).

### Command-line install

```powershell
# Windows (PowerShell)
Copy-Item .\formula_surface.py "$env:APPDATA\ingetrazo\plugins\"
```

```bash
# Linux
cp formula_surface.py ~/.local/share/ingetrazo/plugins/
```

After restarting, the plugin appears as:
- **Extensions ▸ Formula Surface** (menu entry)
- **Formula Surface** tab in the side tray/panel area

## Usage

1. Open **Extensions ▸ Formula Surface** (or switch to the **Formula Surface** panel tab).
2. Enter a formula in `x` and `y` (example: `x**2 + y**2`).
3. Set the **X range**, **Y range**, and **Divisions**.
4. Adjust **Z scale** and **Smooth shading** if needed.
5. Click **Build surface** (or press `Ctrl+Enter`).

The generated surface is added to the active document as one selected group. You can undo it with a single `Ctrl+Z`.

### Formula syntax notes

- Use `**` for powers (not `^`). Example: `x**2 + y**2`
- Prefixes like `z = ...`, `f(x, y) = ...`, and `z(x, y) = ...` are accepted
- Available names include `x`, `y`, `math`, and common math functions/constants such as:
  - `sin`, `cos`, `tan`, `asin`, `acos`, `atan`, `atan2`
  - `sqrt`, `exp`, `log`, `log10`
  - `abs`, `min`, `max`, `pow`, `round`
  - `pi`, `e`, `tau`
- Invalid/undefined sample points are skipped (reported in the status message)

### Tips

- Increase **Divisions X/Y** for smoother/denser surfaces (higher values create more faces).
- Use **Z scale** to resize the height when the formula outputs values in a different scale than meters.
- If a surface disappears near part of the domain, check for invalid points (e.g. `sqrt(...)` of negative values) and adjust the ranges.

## Included examples

The plugin ships with ready-made examples showing the Python formula alongside the common mathematical expression, including:

- Elliptic paraboloid (bowl): `z = x**2 + y**2` (z = x² + y²)
- Stretched elliptic paraboloid: `z = x**2/4 + y**2/9` (z = x²/4 + y²/9)
- Hyperbolic paraboloid (saddle): `z = x**2 - y**2` (z = x² − y²)
- Hyperbolic paraboloid (rotated): `z = x*y` (z = x·y)
- Inclined plane: `z = x + y` (z = x + y)
- Hemisphere (radius 3): `z = sqrt(9 - x**2 - y**2)` (z = √(9 − x² − y²))
- Ellipsoidal dome: `z = sqrt(1 - x**2/9 - y**2/16)` (z = √(1 − x²/9 − y²/16))
- Cone (upper nappe): `z = sqrt(x**2 + y**2)` (z = √(x² + y²))
- Square pyramid: `z = max(abs(x), abs(y))` (z = max(|x|, |y|))
- Diamond pyramid: `z = abs(x) + abs(y)` (z = |x| + |y|)
- Gaussian bell: `z = exp(-(x**2 + y**2))` (z = e^(−(x² + y²)))
- Lorentzian hill: `z = 1/(1 + x**2 + y**2)` (z = 1/(1 + x² + y²))
- Egg-crate surface: `z = sin(x)*cos(y)` (z = sin(x)·cos(y))
- Concentric ripples: `z = sin(sqrt(x**2 + y**2))` (z = sin(√(x² + y²)))
- Sombrero (Mexican hat): `z = sin(sqrt(x**2 + y**2))/(sqrt(x**2 + y**2) + 1e-9)` (z = sin(√(x² + y²)) / (√(x² + y²) + ε))
- Monkey saddle: `z = x**3 - 3*x*y**2` (z = x³ − 3xy²)
- Logarithmic bowl: `z = log(x**2 + y**2 + 1)` (z = ln(x² + y² + 1))
- Twisted wave: `z = sin(x*y)` (z = sin(x·y))
- Damped radial waves: `z = exp(-(x**2 + y**2)/20)*sin(2*sqrt(x**2 + y**2))` (z = e^(−(x² + y²)/20)·sin(2√(x² + y²)))
- Damped egg-crate: `z = sin(3*x)*cos(3*y)*exp(-(x**2 + y**2)/20)` (z = sin(3x)·cos(3y)·e^(−(x² + y²)/20))
- Wavy sheet: `z = sin(x) + sin(y)` (z = sin(x) + sin(y))

## Programmatic API

The module can also be imported and used from Python code inside IngeTrazo:

```python
from formula_surface import build_surface_group, compile_formula, FormulaError

# Build a surface group (mesh + metadata) without adding it to the scene
result = build_surface_group(
    "x**2 + y**2",
    x_min=-2, x_max=2,
    y_min=-2, y_max=2,
    divisions_x=64, divisions_y=64,
    z_scale=1.0,
    smooth=True,
    name="Paraboloid",
)

# result.group -> core.group.Group
# result.faces, result.grid_points, result.valid_points, result.skipped_points
```

`build_surface_group(...)` raises `FormulaError` for user-fixable issues (invalid expression, invalid ranges, no valid points/faces, etc.).

## Security note

Formulas are evaluated with Python `eval` in a restricted namespace (math-related names only, builtins disabled). This is intended for mathematical expressions, but it is still local Python evaluation: **do not run formulas from untrusted sources**.

## Limitations

- Maximum grid resolution is limited to **160 divisions per direction**.
- Very high resolutions and/or complex expressions can take longer to compute.
- Surfaces are generated as quad meshes over a rectangular `(x, y)` domain (not parametric surfaces in `u,v`).
- Regions where the expression is undefined produce holes/gaps (cells are skipped).

## Troubleshooting

- **Plugin/menu not visible:** confirm `formula_surface.py` is in the correct plugins folder and restart IngeTrazo.
- **"Use ** for powers, not ^"**: write `x**2` instead of `x^2`.
- **No surface generated**: check the status message for domain/math errors (e.g. negative sqrt domain) and adjust ranges/divisions.
- **Surface is too flat/tall**: adjust **Z scale**.
- **Panel issues after update**: restart IngeTrazo to reload the plugin cleanly.

## Development

This is a single-file plugin (`formula_surface.py`) with no build step.

- Logging namespace: `ingetrazo.plugins.formula_surface`
- Plugin entry point: `setup(app)`
- Core APIs used: `core.group.Group`, `core.mesh.Mesh`, `core.history.Command`, viewport scene/history integration

## License

GPL-3.0-or-later, as declared in the source file's SPDX header. If you publish this plugin in its own repository, include a matching `LICENSE` file.
