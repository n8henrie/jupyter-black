"""Tests for jupyter_black helpers."""

from conftest import make_cell, source_from_cell


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


def test_source_from_cell() -> None:
    """Test the source_from_cell helper function."""
    cells = {
        "cells": [
            make_cell(cell)  # type: ignore
            for cell in [
                {
                    "source": ["before"],
                },
                {
                    "id": "staticid",
                    "metadata": "fakemd",
                    "source": ["fake", "source"],
                },
                {
                    "source": ["after"],
                },
            ]
        ]
    }
    source = source_from_cell(cells, "staticid")
    assert source == ["fake", "source"]
