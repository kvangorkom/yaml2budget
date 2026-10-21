"""Command line: build the viewer page from a directory of budget YAML files."""
import argparse
import pathlib
import sys

from .budget import ROLLUPS, encode_fonts, load_all, render


def main(argv=None):
    parser = argparse.ArgumentParser(prog='pbudget', description=__doc__)
    parser.add_argument('dir', type=pathlib.Path)
    parser.add_argument('-o', '--out', type=pathlib.Path, default=pathlib.Path('budgets.html'))
    parser.add_argument('--rollup', choices=ROLLUPS, default='rss',
                        help='roll-up for files that do not set one')
    parser.add_argument('--inline', type=pathlib.Path, nargs='+', metavar='JS',
                        help='inline these .js files instead of loading them from the CDN')
    parser.add_argument('--font', type=pathlib.Path, nargs='+', metavar='TTF',
                        help='inline these TTFs (regular [bold]) for PDF text')
    args = parser.parse_args(argv)
    try:
        pages = load_all(args.dir, args.rollup)
    except ValueError as error:
        sys.exit(f'error: {error}')
    args.out.write_text(render(pages, args.inline or (),
                               encode_fonts(args.font) if args.font else None))
    print(f'wrote {args.out}: ' + ', '.join(page['name'] for page in pages))


if __name__ == '__main__':
    main()
