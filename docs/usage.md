# Using yaml2budget

```bash
pip install yaml2budget                       # or: pip install -e .[dev]  (from a checkout)

yaml2budget examples -o budgets.html          # libraries from jsDelivr
yaml2budget examples --rollup sum             # default roll-up for files that do not set one
yaml2budget examples -o budgets.html \
    --inline plotly.min.js jspdf.umd.min.js svg2pdf.umd.min.js \
    --font DejaVuSans.ttf DejaVuSans-Bold.ttf      # fully self-contained (~7 MB)

python examples/make_data.py              # regenerate the example CSVs
python -m unittest discover -s tests -v   # 76 tests
```

The same thing from Python:

```python
from yaml2budget import load_all, render

pages = load_all('examples', default_rollup='sum')
open('budgets.html', 'w').write(render(pages))
```

## The page

`yaml2budget.budget` parses, resamples and rolls up; `yaml2budget/template.html` holds all CSS/JS and
takes the data at `/*DATA*/`. The page has three views: **Table** (hierarchy as columns, roll-ups
as shaded rows), **Flowchart** (left-to-right tree), and **Spectrum** (Plotly, vector budgets
only). A λ slider drives the table and flowchart; clicking the plot also sets λ. Wavelength-dependent
entries carry a sparkline in both the table and the flowchart cards. Margins are shown as a
percentage of the allocation and as a difference in budget units.

**Views**: `views:` in a budget picks the views it offers — a list (`views: [table, spectrum]`),
a single name (`views: flowchart`) or flags (`views: {table: true, spectrum: false}`). All three by
default; the switcher disappears when a budget offers only one, and the spectrum is offered only
for a budget that has a wavelength grid. A `derived:` budget may set its own.

**Phones** (≤640px wide): the toolbar is compact and the λ slider takes its own row; the table
collapses its level columns into one indented column so the numbers are on screen; the flowchart
fits the width when that stays legible and otherwise opens at the root card; the spectrum puts its
legend under the plot. The desktop layout is untouched.

**Theme**: the ◐ button cycles auto (follows the OS) → ☀ light → ☾ dark, remembered per browser.
**Keyboard**: ← / → step the wavelength, shift for ten steps at a time.

**Exports** (PDF via jsPDF + svg2pdf.js, from the CDN or inlined with `--inline`; the Excel
writer is built in, no library):

| button | view | result |
|---|---|---|
| Export YAML | table | the tree with the values at the current λ, in the input schema (re-readable by `yaml2budget.py`) |
| Export Excel | table | a formatted .xlsx: the table at the current λ, plus a *Spectrum* sheet of every term over the band |
| Export PDF | flowchart | a one-page vector PDF the size of the diagram, downloaded directly |
| Export PDF / PNG | spectrum | the same for the plot, or a 2× PNG; both always drawn in light colors |

The exported YAML carries `margin` (difference) and `margin_frac` alongside each `cbe`/`alloc`;
re-reading it recomputes both and warns, so a stale export can never masquerade as input.

The workbook keeps the formatting that carries meaning: frozen header, bold shaded roll-up rows,
Excel row grouping (the +/- outline mirrors the hierarchy), margins as signed percentages coloured
by sign, scientific format for very large or small numbers, and column widths. It is written
directly as OOXML in a stored (uncompressed) ZIP, so no spreadsheet library is involved.

PDF text needs a Unicode face (jsPDF's built-in fonts are Latin-1 only): DejaVu Sans is fetched once
from the CDN, or inlined with `--font`. Without it the text falls back to ASCII (`µrad` → `urad`).
Status marks (✓ ✕ ▲) and the minus sign are always substituted — no PDF-embeddable face carries them.

## YAML schema

One budget per `*.yaml` file. Every node has the same shape; nest to any depth.
Children can be a `children:` list or named sub-mappings (`telescope: {...}`, name = key).
Aliases: `allocation`/`spec` → `alloc`, `description` → `notes`, `multiplier`/`quantity` → `count`. A root holding a single
child and no values (e.g. `total:`) is merged into that child; its text becomes the page's
"About this budget". A supplied parent `cbe` or `margin` is replaced by the computed value
(roll-up; fractional margin as defined below) and a warning is printed for each replacement.

**Extra keys**: any other key on a node (e.g. `source`, `state`, `tbr`) becomes a table column (after Notes),
filled for the nodes that have it (one column set per budget, in first-seen order; hide columns
with the **Columns** menu). Numbers are formatted, lists joined, and long or multi-line text is
collapsed behind its first line. Extras also appear in the flowchart hover text.

| key | where | meaning |
|---|---|---|
| `name` | any node | required |
| `cbe` | leaves | value (see below). Parent CBEs are always computed. |
| `alloc` / `spec` | any node | allocation or requirement (optional) |
| `children` | any node | list of nodes |
| `count` | any node but the root | how many identical copies of this term its parent rolls up (default 1); `cbe` and `alloc` stay per copy. See below. |
| `rollup` | any node | `rss` · `product` · `sum` · `inverse_rss`; inherited by descendants. Root default `rss` (or `--rollup`). |
| `notes` | any node | free text |
| `units` | root | display units, shared by the whole budget |
| `better` | root | `higher` or `lower`; default `higher` for `product`, else `lower` |
| `levels` | root | column headings per depth, e.g. `[Instrument, Subsystem, Element]` |
| `wavelength` | root | `[min, max, step]` grid. Omitted → common range of all tables, 1-2-5 step, ≥200 points |
| `wavelength_units` | root | default `nm` |
| `views` | root | which views to offer: `table` · `flowchart` · `spectrum`. Default all three |
| `margin`, `margin_frac` | any node | replaced by the computed margin (warning printed); written by the YAML export |
| `margin_warn` | root | margin fraction below which a pass is flagged ▲ (default 0.1) |
| `derived` | root | list of `{name, units, scale, alloc, invert, rollup, better}` budgets computed from this one |

**Values** are a number, a CSV path (relative to the YAML; columns `wavelength, value`;
a non-numeric header row is skipped), or an inline table `[[wl, v], ...]`.

**Repeated terms**: `count: N` stands for N identical copies of a node — five mirrors with the same
coating are one entry with the reflectance curve and `count: 5`. Its own `cbe`, `alloc` and margin
stay per copy; what it contributes to the parent is what N copies roll up to under the parent's
operator: `product` → vᴺ, `sum` → N·v, `rss` → √N·v (independent errors), `inverse_rss` → v/√N.
A node with children can be repeated too (e.g. two identical cameras). Any positive number is
accepted. The page marks the term with a ×N pill in the table, a ×N bubble on its edge into the
parent in the flowchart (hover for the combined value) and ×N in the spectrum legend; the YAML
export keeps `count` and the Excel export adds a *Count* column.

```yaml
- {name: Mirrors, cbe: data/al_mgf2_reflectance.csv, count: 5}
```

`inverse_rss` combines reciprocals in quadrature (1/R² = Σ 1/Rᵢ²), which is how resolving powers
and other "higher is better" reciprocal quantities add up; it defaults to `better: higher`.

**Derived budgets** (e.g. resolving power from spatial resolution) copy the evaluated tree and
multiply every CBE and allocation by `scale` (number, CSV, or inline table). With `invert: true`
each value becomes `scale / value` instead, which turns a resolution budget into a resolving power
R = λ/Δλ: with `scale` = λ/dispersion, R = scale/blur. That is consistent with the roll-up, since
scale/RSS(terms) equals the inverse-RSS of scale/termᵢ — so pair it with `rollup: inverse_rss`.
`alloc` overrides the
scaled top-level allocation.

## Assumptions

- Tables are linearly interpolated onto the grid; values beyond a table's range are held
  constant (a warning is printed).
- All entries in a budget share one unit; no unit conversion is done.
- Margin = `1 − CBE/alloc` (lower is better) or `CBE/alloc − 1` (higher is better).
  "Worst in band" is the minimum margin over the grid.
- Derived budgets assume a roll-up that scales linearly (`rss`, `sum`); scaling a
  `product` budget does not give a meaningful result.
- A multi-channel instrument should use one YAML per channel (each has one grid).
- Values are rounded to 5 significant figures in the page.

## Tests

`python -m unittest discover -s tests` covers the roll-up operators on scalars and
vectors at every level of a tree, roll-up inheritance and per-node overrides, grid choice and
interpolation (including clamping), margins in both senses, the replacement of supplied parent
CBEs and margins, schema normalization (aliases, mapping children, wrapper roots), derived
budgets, view selection, the page data (ordering, columns, JSON safety) and the generated file
end to end. Seven further tests drive the page's Excel export in a headless browser and read the
workbook back; they are skipped unless `playwright` and `openpyxl` are installed.
Expected values are written out by hand or computed independently of the code under test.
