"""Tests for jupyter_black running in jupyter notebook."""

import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

from conftest import source_from_cell

import pytest

from jupyter_black.jupyter_black import BlackFormatter


def test_load(notebook: t.Callable) -> None:
    """Test loading with `jupyter_black.load()`."""
    cells = [
        {
            "source": ["import jupyter_black"],
        },
        {
            "source": ["jupyter_black.load(line_length=79)"],
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


def test_empty_cell(notebook: t.Callable) -> None:
    """Empty cells shouldn't break things."""
    cells = [
        {
            "source": ["import jupyter_black"],
        },
        {
            "source": ["jupyter_black.load(line_length=79)"],
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


def test_bad_config() -> None:
    """Ensure only black.Mode options are passed to black.Mode.

    Black options from pyproject.toml should be filtered out if not valid
    black.Mode options.
    """
    mock = MagicMock(return_value=f"{Path(__file__).parent}/pyproject.toml")
    with patch("black.find_pyproject_toml", mock):
        try:
            formatter = BlackFormatter(None)  # type: ignore
        except TypeError as e:
            pytest.fail(f"Failed to instantiate formatter: {e}")
    assert formatter.mode.line_length == 42


def test_notebook_loadext(notebook: t.Callable) -> None:
    """Test loading with %load_ext magic, supported since notebook 7 or so."""
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
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "magic_singlequotes")
    assert fix_quotes_with_magic[-1] == 'print("foo")'
