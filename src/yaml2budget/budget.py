"""Reading budget YAML, rolling it up and rendering the viewer page.

Each *.yaml is one budget tree (schema: docs/usage.md). Values are scalars, CSV paths
(wavelength, value) or inline [[wavelength, value], ...] tables. Tables are interpolated onto
one wavelength grid per budget and parents are rolled up here; the page only indexes the
result.
"""
import base64
import copy
import importlib.resources
import json
import pathlib
import sys
from functools import reduce

import numpy as np
import yaml

ROLLUPS = {
    'product': lambda vals: reduce(np.multiply, vals),
    'sum': lambda vals: reduce(np.add, vals),
    'rss': lambda vals: np.sqrt(reduce(np.add, [np.square(v) for v in vals])),
    # resolving powers and other reciprocal quantities: 1/R^2 = sum 1/R_i^2
    'inverse_rss': lambda vals: 1 / np.sqrt(reduce(np.add, [1 / np.square(v) for v in vals])),
}
HIGHER_IS_BETTER = ('product', 'inverse_rss')
CDN = [
    'https://cdn.jsdelivr.net/npm/plotly.js-dist-min@3.7.0/plotly.min.js',    # spectrum view
    'https://cdn.jsdelivr.net/npm/jspdf@4.2.1/dist/jspdf.umd.min.js',         # PDF export
    'https://cdn.jsdelivr.net/npm/svg2pdf.js@2.8.1/dist/svg2pdf.umd.min.js',
]
ALIASES = {'allocation': 'alloc', 'spec': 'alloc', 'description': 'notes'}
NODE_KEYS = {'name', 'cbe', 'alloc', 'children', 'rollup', 'notes'}   # keys with their own column
BUDGET_KEYS = {'units', 'better', 'levels', 'wavelength', 'wavelength_units', 'margin_warn',
               'derived', 'description', 'views'}
VIEWS = {'table': 'table', 'flowchart': 'flow', 'spectrum': 'plot',   # YAML name -> page id
         'flow': 'flow', 'plot': 'plot'}
MARGIN_KEYS = ('margin', 'margin_frac')
MIN_POINTS = 200                                     # grid resolution when none is given
TEMPLATE = importlib.resources.files(__package__) / 'template.html'


def normalize(node, name=None):
    """Canonical node: aliases renamed, dict-valued keys turned into children named by their key."""
    node = {ALIASES.get(key, key): value for key, value in node.items()}
    children = [normalize(child) for child in node.pop('children', [])]
    nested = [key for key, value in node.items()                 # a mapping is a child, unless
              if isinstance(value, dict) and key not in BUDGET_KEYS]   # it is a budget setting
    children += [normalize(node[key], key) for key in nested]
    node = {key: value for key, value in node.items() if key not in nested}
    node.setdefault('name', name)
    return {**node, 'children': children} if children else node


def walk(node):
    """Yield a node and all of its descendants, parents first."""
    yield node
    for child in node.get('children', []):
        yield from walk(child)


def read_value(value, base):
    """Scalar -> float; CSV path or inline pairs -> (wavelengths, values); 1-row table -> float."""
    if value is None or isinstance(value, (int, float)):
        return value
    rows = (np.genfromtxt(base / value, delimiter=',', ndmin=2) if isinstance(value, str)
            else np.array(value, dtype=float))
    rows = rows[~np.isnan(rows[:, :2]).any(axis=1)]           # drop header / blank rows
    return float(rows[0, 1]) if len(rows) == 1 else (rows[:, 0], rows[:, 1])


def make_grid(budget, tables):
    """The budget's `wavelength: [min, max, step]`, else a 1-2-5 step over the common range."""
    if 'wavelength' in budget:
        lo, hi, step = budget['wavelength']
    elif tables:
        lo = max(wavelengths.min() for wavelengths, _ in tables)
        hi = min(wavelengths.max() for wavelengths, _ in tables)
        if hi <= lo:
            raise ValueError(f'{budget["name"]}: tables share no wavelength range; '
                             'set `wavelength:`')
        decade = 10.0 ** np.floor(np.log10((hi - lo) / MIN_POINTS))
        step = next(m * decade for m in (5, 2, 1) if (hi - lo) / (m * decade) >= MIN_POINTS)
        lo = np.ceil(lo / step) * step
    else:
        return None
    return np.arange(lo, hi + step / 2, step)


def margins(cbe, alloc, better):
    """(difference, fraction of the allocation) left; positive means the budget is met."""
    if alloc is None:
        return None, None
    if better == 'higher':
        return cbe - alloc, cbe / alloc - 1
    return alloc - cbe, 1 - cbe / alloc


def describe(value):
    """Short text for a scalar or vector, used in the replacement warnings."""
    if value is None:
        return 'n/a (no alloc)'
    if np.ndim(value) == 0:
        return f'{value:.4g}'
    return f'{np.min(value):.4g}..{np.max(value):.4g}'


def evaluate(budget, src, default_rollup='rss'):
    """Load values (relative to YAML file `src`), pick a grid, roll parents up in place.

    Returns the grid, or None for a budget of scalars only. Supplied parent CBEs and margins
    are replaced by the computed ones, with a warning on stderr for each replacement.
    """
    base = src.parent
    nodes = list(walk(budget))
    for node in nodes:
        node['cbe'] = read_value(node.get('cbe'), base)
        node['alloc'] = read_value(node.get('alloc'), base)

    tables = [value for node in nodes for value in (node['cbe'], node['alloc'])
              if isinstance(value, tuple)]
    grid = make_grid(budget, tables)
    better = budget.setdefault(
        'better', 'higher' if budget.get('rollup', default_rollup) in HIGHER_IS_BETTER else 'lower')

    def warn(message):
        print(f'warning [{src.name}] {message}', file=sys.stderr)

    def replaced(path, key, supplied, computed):
        warn(f'{path}: supplied {key} {describe(supplied)} '
             f'replaced by computed {describe(computed)}')

    def on_grid(value):
        return np.interp(grid, *value) if isinstance(value, tuple) else value

    def roll(node, inherited, parent_path):
        path = f'{parent_path}/{node["name"]}' if parent_path else node['name']
        rollup = node.setdefault('rollup', inherited)
        children = node.get('children', [])
        node['alloc'] = on_grid(node['alloc'])
        if children:
            computed = ROLLUPS[rollup]([roll(child, rollup, path) for child in children])
            if node['cbe'] is not None:
                replaced(path, 'cbe', on_grid(node['cbe']), computed)
            node['cbe'] = computed
        elif node['cbe'] is None:
            raise ValueError(f'{budget["name"]}: leaf "{path}" has no cbe')
        else:
            node['cbe'] = on_grid(node['cbe'])
        for key, computed in zip(MARGIN_KEYS, margins(node['cbe'], node['alloc'], better)):
            if key in node:
                replaced(path, key, node.pop(key), computed)
        return node['cbe']

    for wavelengths, _ in tables:
        if grid[0] < wavelengths.min() or grid[-1] > wavelengths.max():
            warn(f'table {wavelengths.min():g}-{wavelengths.max():g} clamped to grid')
    roll(budget, default_rollup, '')
    return grid


def derive(budget, spec, grid, base):
    """Copy of an evaluated budget with every value scaled by `spec['scale']`.

    With `invert: true` each value becomes `scale / value` instead, which turns a resolution
    budget into a resolving power (R = lambda / dlambda). That is consistent with the roll-up:
    scale / rss(terms) equals inverse_rss(scale / term), so nothing has to be rolled up again.
    """
    scale = read_value(spec['scale'], base)
    scale = np.interp(grid, *scale) if isinstance(scale, tuple) else scale
    convert = (lambda v: scale / v) if spec.get('invert') else (lambda v: v * scale)
    out = {**copy.deepcopy(budget),
           **{key: value for key, value in spec.items() if key not in ('scale', 'alloc', 'invert')}}
    for node in walk(out):
        node['cbe'] = convert(node['cbe'])
        node['alloc'] = None if node['alloc'] is None else convert(node['alloc'])
        if 'rollup' in spec:                      # the operator the converted tree now obeys
            node['rollup'] = spec['rollup']
    out['alloc'] = spec.get('alloc', out['alloc'])
    return out


def rounded(value):
    """JSON-friendly value, 5 significant figures."""
    if value is None:
        return None
    if np.ndim(value) == 0:
        return float(f'{value:.5g}')
    return [float(f'{v:.5g}') for v in value]


def displayed(value):
    """Extra-key value for display: scalars as-is, lists joined, anything else as text."""
    if isinstance(value, (int, float, str, bool)):
        return value
    return ', '.join(map(str, value)) if isinstance(value, list) else str(value)


def flatten(budget, grid):
    """Evaluated tree -> what the page indexes: a depth-first node list plus the page settings."""
    nodes = []

    def add(node, parent, depth):
        skip = NODE_KEYS | (BUDGET_KEYS if parent is None else set())
        nodes.append(dict(
            parent=parent, depth=depth, name=node['name'], notes=node.get('notes', ''),
            op=node['rollup'] if node.get('children') else None,
            cbe=rounded(node['cbe']), alloc=rounded(node['alloc']),
            extra={key: displayed(value) for key, value in node.items()
                   if key not in skip and value is not None}))
        index = len(nodes) - 1
        for child in node.get('children', []):
            add(child, index, depth + 1)

    add(budget, None, 0)
    return dict(
        name=budget['name'], units=budget.get('units', ''), levels=budget.get('levels', []),
        description=budget.get('description', ''), better=budget['better'],
        warn=budget.get('margin_warn', 0.1), wl_units=budget.get('wavelength_units', 'nm'),
        grid=rounded(grid), views=page_views(budget), nodes=nodes,
        columns=list(dict.fromkeys(key for node in nodes for key in node['extra'])))


def page_views(budget):
    """Views this budget offers: `views:` as a list or {name: bool} map, else all three."""
    wanted = budget.get('views', list(VIEWS)[:3])
    if isinstance(wanted, dict):
        wanted = [name for name, on in wanted.items() if on]
    elif isinstance(wanted, str):
        wanted = [wanted]
    unknown = [name for name in wanted if name not in VIEWS]
    if unknown:
        raise ValueError(f'{budget["name"]}: unknown view(s) {", ".join(map(str, unknown))}; '
                         f'pick from {", ".join(list(VIEWS)[:3])}')
    views = list(dict.fromkeys(VIEWS[name] for name in wanted))
    if not views:
        raise ValueError(f'{budget["name"]}: `views:` leaves no view enabled')
    return views


def load_budget(path, default_rollup='rss'):
    """Read and evaluate one YAML file. Returns (budget, grid)."""
    budget = normalize(yaml.safe_load(path.read_text()), path.stem)
    budget['description'] = budget.pop('notes', '').strip().strip("'").strip()
    children = budget.get('children', [])
    if len(children) == 1 and not {'cbe', 'alloc'} & budget.keys():   # wrapper root, e.g. `total:`
        budget = {**budget, **children[0], 'name': budget['name']}
    return budget, evaluate(budget, path, default_rollup)


def load_all(directory, default_rollup='rss'):
    """Every *.yaml in `directory`, plus its derived budgets, as page-ready dicts."""
    pages = []
    for path in sorted(pathlib.Path(directory).glob('*.y*ml')):
        budget, grid = load_budget(path, default_rollup)
        found = [flatten(budget, grid)]
        found += [flatten(derive(budget, spec, grid, path.parent), grid)
                  for spec in budget.get('derived', [])]
        pages += [{**page, 'file': path.name} for page in found]
    names = [page['name'] for page in pages]
    for page in pages:                                # disambiguate budgets that share a name
        if names.count(page['name']) > 1:
            page['name'] += f' ({page["file"]})'
    return pages


def encode_fonts(paths):
    """{style: base64 TTF} for the PDF export; the bold face falls back to the regular one."""
    encoded = [base64.b64encode(path.read_bytes()).decode() for path in paths]
    return dict(normal=encoded[0], bold=encoded[1] if len(encoded) > 1 else encoded[0])


def render(pages, inline=(), fonts=None):
    """The finished HTML: template + data + either CDN script tags or inlined libraries."""
    scripts = ('\n'.join(f'<script>{path.read_text()}</script>' for path in inline) if inline
               else '\n'.join(f'<script src="{url}"></script>' for url in CDN))
    if fonts:
        scripts += f'\n<script>window.PB_FONT={json.dumps(fonts)}</script>'
    data = json.dumps(pages, ensure_ascii=False).replace('</', r'<\/')
    return TEMPLATE.read_text().replace('/*DATA*/', data).replace('<!--SCRIPTS-->', scripts)


__all__ = ['ROLLUPS', 'HIGHER_IS_BETTER', 'CDN', 'VIEWS', 'MIN_POINTS', 'TEMPLATE', 'ALIASES',
           'NODE_KEYS',
           'BUDGET_KEYS', 'MARGIN_KEYS', 'normalize', 'walk', 'read_value',
           'make_grid', 'margins', 'describe', 'evaluate', 'derive', 'rounded', 'displayed',
           'flatten', 'page_views', 'load_budget', 'load_all', 'encode_fonts', 'render']
