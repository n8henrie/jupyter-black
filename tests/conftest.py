"""Provide pytest fixtures for jupyter_black tests."""

import json
import os
import socket
import subprocess
import sys
import typing as t
from itertools import count
from pathlib import Path
from uuid import uuid4

import pytest
from _pytest.fixtures import SubRequest
from playwright.sync_api import Page, Response, sync_playwright, WebSocket
from pytest import TempPathFactory

# Use different port for 3.7 vs 3.8 to allow parallel tox runs
PORT = sys.version_info[1] + 52750

base_notebook = {
    "cells": [],
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

# Should be atomic: https://stackoverflow.com/a/27062830/1588795
id_counter = count()


def make_cell(cell: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Fill in defaults for a generic code cell and generate unique id.

    Does not override any existing content.
    """
    unique_id = str(next(id_counter))
    preset_id = cell.get("id")
    if preset_id:
        unique_id = f"{unique_id}-{preset_id}"
    template: t.Dict[str, t.Any] = {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
    }
    # Override template with cell
    full_cell = {**template, **cell}
    full_cell["id"] = unique_id
    return full_cell


def all_cells_run(event_str: str, expected_count: int) -> bool:
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


def is_saved(response: Response, name: str) -> bool:
    """Wait for the response showing that saving has taken place."""
    expected_url = f"http://localhost:{PORT}/api/contents/{name}"
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


def _jupyter_output(
    page: Page, tmp: Path, json_input: t.Dict[str, t.Any]
) -> t.Dict[str, t.Any]:
    notebook_content = base_notebook

    cells = t.cast(t.List, notebook_content["cells"])
    cells.extend(json_input)
    notebook_content["cells"] = [make_cell(cell) for cell in cells]

    name = f"notebook-{uuid4()}.ipynb"
    nb = Path(tmp) / name
    nb.write_text(json.dumps(notebook_content))
    url_base = f"http://localhost:{PORT}"

    notebook_url = f"{url_base}/notebooks/{name}"
    with page.expect_websocket(kernel_ready) as ws_info:
        page.goto(notebook_url)
    ws = ws_info.value

    # Blank cells do not increment execution_count
    expected_count = sum(1 for cell in cells if cell["source"])

    page.click("#celllink")
    with ws.expect_event(
        "framereceived", lambda event: all_cells_run(event, expected_count)
    ):
        page.click("text=Run All")

    with page.expect_response(lambda resp: is_saved(resp, name)) as resp:
        page.click('button[title="Save and Checkpoint"]')

    page.click("#kernellink")
    page.click("text=Shutdown")
    with page.expect_response(is_closing) as resp:
        page.click('button:has-text("Shutdown")')

    if resp.value.finished() is not None:
        raise Exception("Response never finished")

    return json.loads(nb.read_text())


@pytest.fixture(scope="session")
def jupyter_server(
    request: SubRequest,
    tmp_path_factory: TempPathFactory,
) -> t.Callable:
    """Fixture to run a notebook via Playwright.

    Seems like an actual browser is required for the JS to run, but headless
    Playwright seems to be working.

    I think this could be modularized to test both lab and notebook, but
    currently have only spend the time to get it working for notebooks.
    """
    tmp = tmp_path_factory.getbasetemp()
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

    # Wait for jupyter server to be ready
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(("localhost", PORT))
        except (ConnectionRefusedError, OSError):
            continue
        else:
            break

    playwright = sync_playwright().start()
    browser = playwright.firefox.launch(headless=True)

    def close() -> None:
        browser.close()
        playwright.stop()
        proc.terminate()
        proc.wait(timeout=5)

    request.addfinalizer(close)

    context = browser.new_context()
    page = context.new_page()

    url_base = f"http://localhost:{PORT}"
    with page.expect_response(
        lambda resp: "A Jupyter Server is running." in resp.text()
    ):
        page.goto(f"{url_base}")

    return lambda json_in: _jupyter_output(page, tmp, json_input=json_in)
