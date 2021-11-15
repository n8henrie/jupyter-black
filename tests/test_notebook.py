"""Tests for jupyter_black running in jupyter notebook."""

import typing as t

from conftest import source_from_cell


def test_load(notebook: t.Callable) -> None:
    """Test loading with `jupyter_black.load()`."""
    cells = [
        {
            "source": ["import jupyter_black"],
        },
        {
            "source": ["jupyter_black.load(line_length=79, lab=False)"],
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
    output = notebook(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'


def test_notebook_loadext_fails(notebook: t.Callable) -> None:
    """Loading with %load_ext magic fails in notebook.

    Currently the default is `jupyter_black.load(lab=True)`. When loading by
    `%load_ext`, one cannot specify any configuration, so it should fail to
    blacken the cells if loaded this way in notebook.
    """
    cells = [
        {
            "source": ["%load_ext jupyter_black"],
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
    output = notebook(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == "print('foo')"

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == "print('foo')"


def test_empty_cell(notebook: t.Callable) -> None:
    """Empty cells shouldn't break thinks."""
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
    output = notebook(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'
