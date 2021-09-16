"""Test jupyter_black.

Tests for `jupyter_black` module.
"""

import json
import os
import subprocess
import sys
import typing as t
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from playwright.sync_api import sync_playwright

PORT = 8744


@pytest.fixture(scope="module")
def jupyter() -> t.Sequence[str]:
    """Fixture to run the code in a notebook."""
    with TemporaryDirectory() as tmp:
        os.chdir(tmp)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "jupyter",
                "notebook",
                f"--port={PORT}",
                "--no-browser",
                "--NotebookApp.token=''",
                "--NotebookApp.password=''",
            ]
        )
        yield tmp
    proc.terminate()


null = None
notebook = {
    "cells": [
        {
            "cell_type": "code",
            "execution_count": null,
            "id": "587e383e",
            "metadata": {},
            "outputs": [],
            "source": ["import jupyter_black"],
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "id": "4393b5d4",
            "metadata": {},
            "outputs": [],
            "source": ["jupyter_black.load(line_length=79, lab=False)"],
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "id": "e9eb672a",
            "metadata": {},
            "outputs": [],
            "source": ["# %load_ext jupyter_black"],
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "id": "25a6901f",
            "metadata": {},
            "outputs": [],
            "source": ["print('foo')"],
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "id": "25a6801f",
            "metadata": {},
            "outputs": [],
            "source": ["%%time\n", "\n", "# print('foo')\n", "print('foo')"],
        },
        {
            "cell_type": "code",
            "execution_count": null,
            "id": "d0cfb421",
            "metadata": {},
            "outputs": [],
            "source": [],
        },
    ],
    "metadata": {
        "kernelspec": {
            "display_name": "Python 3 (ipykernel)",
            "language": "python",
            "name": "python3",
        },
        "language_info": {
            "codemirror_mode": {"name": "ipython", "version": 3},
            "file_extension": ".py",
            "mimetype": "text/x-python",
            "name": "python",
            "nbconvert_exporter": "python",
            "pygments_lexer": "ipython3",
            "version": "3.9.7",
        },
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}


def all_cells_run(event):
    try:
        event = json.loads(event)
        msg_type = event["msg_type"]
        content = event["content"]
        execution_count = content["execution_count"]
        status = content["status"]
    except (TypeError, KeyError):
        return False

    # Blank cells do not increment execution_count
    expected_count = sum(1 for cell in notebook["cells"] if cell["source"])
    return all(
        (
            msg_type == "execute_reply",
            execution_count == expected_count,
            status == "ok",
        )
    )


def is_saved(response):
    expected_url = (
        f"http://localhost:{PORT}/api/contents/notebook.ipynb/checkpoints"
    )
    id_ = response.json().get("id")
    return all(
        (
            response.url == expected_url,
            id_ == "checkpoint",
            response.finished() is None,
        )
    )


def source_from_cell(content, id):
    return next(
        cell.get("source") for cell in content["cells"] if cell["id"] == id
    )


def kernel_ready(event):
    try:
        event = json.loads(event)
        msg_type = event["msg_type"]
        content = event["content"]
        status = content["status"]
    except (TypeError, KeyError):
        return False

    return all(
        (
            msg_type == "comm_info_reply",
            status == "ok",
        )
    )


def test_jupyter_black(jupyter):
    """Test converting a notebook."""
    nb = Path(jupyter) / "notebook.ipynb"
    nb.write_text(json.dumps(notebook))

    assert json.loads(nb.read_text()) == notebook
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()

        with page.expect_websocket() as ws_info:
            page.goto(
                f"http://localhost:{PORT}/notebooks/notebook.ipynb",
                wait_until="load",
            )

        ws = ws_info.value
        ws.wait_for_event("framereceived", kernel_ready)

        with ws.expect_event("framereceived", all_cells_run):
            page.click("#celllink")
            page.click("text=Run All")

        with page.expect_response(is_saved) as resp:
            page.click('button[title="Save and Checkpoint"]')

        if resp.value.finished():
            browser.close()

    output = json.loads(nb.read_text())

    fix_quotes = source_from_cell(output, "25a6901f")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(output, "25a6801f")
    assert fix_quotes_with_magic[-1] == 'print("foo")'
