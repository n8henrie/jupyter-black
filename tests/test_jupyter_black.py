"""Test jupyter_black.

Tests for `jupyter_black` module.
"""

import json
import os
import socket
import subprocess
import sys
import typing as t
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from _pytest.fixtures import SubRequest
from playwright.sync_api import Response, sync_playwright, WebSocket

# Use different port for 3.7 vs 3.8 to allow parallel tox runs
PORT = sys.version_info[1] + 52750

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


@pytest.fixture(scope="module")
def jupyter_output(request: SubRequest) -> t.Sequence[str]:
    """Fixture to run a notebook via Playwright.

    Seems like an actual browser is required for the JS to run, but headless
    Playwright seems to be working.

    I think this could be modularized to test both lab and notebook, but
    currently have only spend the time to get it working for notebooks.
    """
    with TemporaryDirectory() as tmp, sync_playwright() as p:
        os.chdir(tmp)
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "jupyter",
                "server",
                f"--ServerApp.port={PORT}",
                "--ServerApp.token=''",
                "--ServerApp.password=''",
                "--no-browser",
            ]
        )

        def term() -> None:
            proc.terminate()
            proc.wait(timeout=20)

        request.addfinalizer(term)

        # Wait for jupyter server to be ready
        while True:
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.connect(("localhost", PORT))
            except (ConnectionRefusedError, OSError):
                continue
            else:
                break

        nb = Path(tmp) / "notebook.ipynb"
        nb.write_text(json.dumps(notebook))
        url_base = f"http://localhost:{PORT}"

        browser = p.firefox.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        with page.expect_response(
            lambda resp: "A Jupyter Server is running." in resp.text()
        ):
            page.goto(f"{url_base}")
        with page.expect_websocket(kernel_ready) as ws_info:
            page.goto(f"{url_base}/notebooks/notebook.ipynb")
        ws = ws_info.value

        page.click("#celllink")
        with ws.expect_event("framereceived", all_cells_run):
            page.click("text=Run All")

        with page.expect_response(is_saved) as resp:
            page.click('button[title="Save and Checkpoint"]')

        page.click("#kernellink")
        page.click("text=Shutdown")
        with page.expect_response(is_closing) as resp:
            page.click('button:has-text("Shutdown")')

        if resp.value.finished() is None:
            browser.close()

        output = json.loads(nb.read_text())
    return output


def all_cells_run(event_str: str) -> bool:
    """Wait for an event signalling all cells have run.

    `execution_count` should equal number of nonempty cells.
    """
    try:
        event = json.loads(event_str)
        msg_type = event["msg_type"]
        content = event["content"]
        execution_count = content["execution_count"]
        status = content["status"]
    except (TypeError, KeyError):
        return False

    # Blank cells do not increment execution_count
    expected_count: int = sum(
        1 for cell in notebook["cells"] if cell["source"]  # type: ignore
    )
    return all(
        (
            msg_type == "execute_reply",
            execution_count == expected_count,
            status == "ok",
        )
    )


def is_closing(response: Response) -> bool:
    """Wait for the response showing that the kernel is shutting down."""
    expected_url = f"http://localhost:{PORT}/api/sessions/"
    method = response.request.method
    status_text = response.status_text

    return all(
        (
            response.url.startswith(expected_url),
            method == "DELETE",
            status_text == "No Content",
            response.finished() is None,
        )
    )


def is_saved(response: Response) -> bool:
    """Wait for the response showing that saving has taken place."""
    expected_url = f"http://localhost:{PORT}/api/contents/notebook.ipynb"
    method = response.request.method
    t = response.json().get("type")
    return all(
        (
            response.url == expected_url,
            t == "notebook",
            method == "PUT",
            response.finished() is None,
        )
    )


def source_from_cell(content: t.Dict[str, t.Any], cell_id: str) -> str:
    """Return cell source for a given id."""
    return next(
        cell.get("source")
        for cell in content["cells"]
        if cell["id"] == cell_id
    )


def kernel_ready_event(event_str: str) -> bool:
    """Wait for an event signalling the kernel is ready to run cell.

    Seems like `comm_info_reply` is a reasonable target for `jupyter notebook`
    whereas `kernel_info_reply` works for `jupyter server`.
    """
    try:
        event = json.loads(event_str)
        msg_type = event["msg_type"]
        content = event["content"]
        status = content["status"]
    except (TypeError, KeyError):
        return False

    return all(
        (
            msg_type == "kernel_info_reply",
            status == "ok",
        )
    )


def kernel_ready(ws: WebSocket) -> bool:
    """Wait for the kernel_ready_event on a websocket."""
    with ws.expect_event("framereceived", kernel_ready_event):
        return True


def test_jupyter_black(jupyter_output: t.Dict[str, t.Any]) -> None:
    """Test converting a notebook."""
    fix_quotes = source_from_cell(jupyter_output, "25a6901f")
    assert fix_quotes[-1] == 'print("foo")'

    fix_quotes_with_magic = source_from_cell(jupyter_output, "25a6801f")
    assert fix_quotes_with_magic[-1] == 'print("foo")'
