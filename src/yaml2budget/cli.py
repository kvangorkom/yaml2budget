"""Command line: build the viewer page from a directory of budget YAML files."""
import argparse
import pathlib
import sys

from .budget import ROLLUPS, encode_fonts, load_all, render
from .headless import FORMATS, export


def main(argv=None):
    parser = argparse.ArgumentParser(prog='yaml2budget', description=__doc__)
    parser.add_argument('dir', type=pathlib.Path)
    parser.add_argument('-o', '--out', type=pathlib.Path, default=pathlib.Path('budgets.html'))
    parser.add_argument('--rollup', choices=ROLLUPS, default='rss',
                        help='roll-up for files that do not set one')
    parser.add_argument('--inline', type=pathlib.Path, nargs='+', metavar='JS',
                        help='inline these .js files instead of loading them from the CDN')
    parser.add_argument('--font', type=pathlib.Path, nargs='+', metavar='TTF',
                        help='inline these TTFs (regular [bold]) for PDF text')
    parser.add_argument('--export', type=pathlib.Path, metavar='DIR',
                        help='also write the page\'s exports for every budget into DIR '
                             '(needs: pip install "yaml2budget[export]")')
    parser.add_argument('--formats', nargs='+', choices=FORMATS,
                        help='exports to write (default: all)')
    parser.add_argument('--wavelength', type=float, metavar='WL',
                        help='evaluate exports at the grid point nearest WL '
                             '(default: the start of the band)')
    args = parser.parse_args(argv)
    if not args.export and (args.formats or args.wavelength is not None):
        parser.error('--formats and --wavelength only apply with --export')
    try:
        pages = load_all(args.dir, args.rollup)
    except ValueError as error:
        sys.exit(f'error: {error}')
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(pages, args.inline or (),
                               encode_fonts(args.font) if args.font else None))
    print(f'wrote {args.out}: ' + ', '.join(page['name'] for page in pages))
    if args.export:
        try:
            export(args.out, args.export, args.formats or list(FORMATS), args.wavelength)
        except RuntimeError as error:
            sys.exit(f'error: {error}')


if __name__ == '__main__':
    main()
