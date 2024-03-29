"""Tests for jupyter_black running in jupyter notebook."""

import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from conftest import source_from_cell
from playwright.sync_api import Error as PWError

from jupyter_black.jupyter_black import BlackFormatter


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


def test_load_ext_fails(notebook: t.Callable) -> None:
    """Fail with `%load_ext jupyter_black`.

    Currently the default is `jupyter_black.load(lab=True)`. When loading by
    `%load_ext`, one cannot specify any configuration, so it should fail in a
    non-lab notebook.

    Currently, the behavior is to present a javascript `alert` and log to the
    console if it seems like a non-lab notebook is being loaded with
    `lab=True`. The test environment will see this dialog
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

    with pytest.raises(PWError):
        _ = notebook(cells)


def test_empty_cell(notebook: t.Callable) -> None:
    """Empty cells shouldn't break things."""
    cells = [
        {
            "source": ["import jupyter_black"],
        },
        {
            "source": ["jupyter_black.load(line_length=79, lab=False)"],
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
