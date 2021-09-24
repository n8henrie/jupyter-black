"""Test jupyter_black.

Tests for `jupyter_black` module.
"""

import typing as t

from conftest import make_cell


def source_from_cell(content: t.Dict[str, t.Any], cell_id: str) -> str:
    """Return cell source for a given id.

    Jupyter doesn't like if cell ids are not totally unique (including between
    notebooks apparently), so I append a hyphen and an incrementing number.
    This takes that into consideration and returns the cell with an otherwise
    matching id.
    """
    return next(
        cell.get("source")
        for cell in content["cells"]
        if cell["id"].rsplit("-", 1)[-1] == cell_id
    )


def test_load(jupyter_server: t.Callable) -> None:
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
    output = jupyter_server(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'


def test_load_ext(jupyter_server: t.Callable) -> None:
    """Test loading with %load_ext magic."""
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
    output = jupyter_server(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'


def test_empty_cell(jupyter_server: t.Callable) -> None:
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
    output = jupyter_server(cells)
    fix_quotes = source_from_cell(output, "singlequotes")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'


def test_make_cell() -> None:
    """Test the make_cell helper function."""
    cell = {
        "id": "staticid",
        "metadata": "fakemd",
        "source": ["fake", "source"],
    }
    outcell = make_cell(cell)
    assert outcell["source"] == ["fake", "source"]
    assert outcell["id"] != "staticid"
    assert outcell["id"].rsplit("-", -1)[-1] == "staticid"
    assert outcell["metadata"] == "fakemd"
    assert outcell["cell_type"] == "code"
