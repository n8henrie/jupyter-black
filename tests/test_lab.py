"""Tests for jupyter_black running in jupyter lab."""

import typing as t

from conftest import source_from_cell


def test_lab(lab: t.Callable) -> None:
    """Empty cells shouldn't break things."""
    cells = [
        {
            "source": ["import jupyter_black"],
        },
        {
            "source": ["jupyter_black.load(line_length=79, lab=True)"],
        },
        {
            "id": "singlequotes",
            "source": ["print('foo')"],
        },
        {
            "id": "magic_singlequotes",
            "source": ["%%time\n", "\n", "# print('foo')\n", "print('foo')"],
        },
    ]
    output = lab(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'


def test_empty_cell(lab: t.Callable) -> None:
    """Empty cells shouldn't break thinks."""
    cells = [
        {
            "source": ["import jupyter_black"],
        },
        {
            "source": ["jupyter_black.load(line_length=79, lab=True)"],
        },
        {
            "source": [],
        },
        {
            "id": "singlequotes",
            "source": ["print('foo')"],
        },
        {
            "id": "magic_singlequotes",
            "source": ["%%time\n", "\n", "# print('foo')\n", "print('foo')"],
        },
    ]
    output = lab(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'


def test_lab_loadext_fails(lab: t.Callable) -> None:
    """Fail with `%load_ext jupyter_black`.

    Currently the default is `jupyter_black.load(lab=False)`. When loading by
    `%load_ext`, one cannot specify any configuration, so it should fail to
    blacken the cells.
    """
    cells = [
        {
            "source": ["%load_ext jupyter_black"],
        },
        {
            "source": [],
        },
        {
            "id": "singlequotes",
            "source": ["print('foo')"],
        },
        {
            "id": "magic_singlequotes",
            "source": ["%%time\n", "\n", "# print('foo')\n", "print('foo')"],
        },
    ]
    output = lab(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == "print('foo')"

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == "print('foo')"
