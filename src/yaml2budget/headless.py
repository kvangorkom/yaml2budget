"""Export files from a built page without a browser window: the page's own Export buttons,
pressed in headless Chromium (Playwright, `pip install yaml2budget[export]`).

The files are the ones the buttons download, so they match the page exactly.
"""
import pathlib

# format name -> (view it belongs to, export button)
FORMATS = {
    'yaml': ('table', 'exYaml'),
    'excel': ('table', 'exXlsx'),
    'flowchart': ('flow', 'exPdf'),
    'spectrum': ('plot', 'exPdf'),
    'png': ('plot', 'exPng'),
}
VIEWPORT = {'width': 1400, 'height': 900}    # sets the size of the spectrum exports
TIMEOUT = 60_000                             # ms per file; the PDF font may come from the CDN

# Show budget `b` in `view` at the grid point nearest `wl` (or the page's default λ).
SELECT = """([b, view, wl]) => {
  S.b = b; S.view = view;
  const grid = B().grid;
  if (grid && wl != null)
    S.i = grid.reduce((k, x, j) => Math.abs(x - wl) < Math.abs(grid[k] - wl) ? j : k, 0);
  render();
  return grid ? grid[S.i] : null;
}"""
# Views a budget offers (`views:`; the spectrum only with a wavelength grid).
OFFERED = "b => BUDGETS[b].views.filter(v => v !== 'plot' || BUDGETS[b].grid)"


def export(page, out_dir, formats=tuple(FORMATS), wavelength=None, log=print):
    """Write every budget's `formats` from the built page `page` into `out_dir`.

    A format is skipped for a budget that does not offer its view. Returns the written paths.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        raise RuntimeError('exporting needs Playwright: pip install "yaml2budget[export]" '
                           '&& playwright install chromium') from None
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written, errors = [], []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            context = browser.new_context(accept_downloads=True, viewport=VIEWPORT)

            def load():
                tab = context.new_page()
                tab.on('pageerror', lambda error: errors.append(str(error)))
                tab.goto(pathlib.Path(page).resolve().as_uri())
                return tab

            tab = load()
            names = tab.evaluate('BUDGETS.map(b => b.name)')
            for b, name in enumerate(names):
                if b:                       # Chromium blocks a page's downloads after the tenth
                    tab.close()
                    tab = load()
                offered = tab.evaluate(OFFERED, b)
                for fmt in formats:
                    view, button = FORMATS[fmt]
                    if view not in offered:
                        continue
                    at = tab.evaluate(SELECT, [b, view, wavelength])
                    with tab.expect_download(timeout=TIMEOUT) as download:
                        tab.evaluate(f'document.getElementById("{button}").onclick()')
                    path = out_dir / download.value.suggested_filename
                    download.value.save_as(path)
                    written.append(path)
                    where = f' at {at:g}' if at is not None and view != 'plot' else ''
                    log(f'{name}: {fmt}{where} -> {path}')
        finally:
            browser.close()
    if errors:
        raise RuntimeError('page error during export: ' + '; '.join(errors))
    return written
