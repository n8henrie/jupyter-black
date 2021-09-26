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
from _pytest.config import Config
from _pytest.config.argparsing import Parser
from _pytest.fixtures import SubRequest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Response,
    sync_playwright,
    WebSocket,
)
from pytest import TempPathFactory


def _base_notebook() -> t.Dict:
    return {
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


def is_closing(response: Response, port: int) -> bool:
    """Wait for the response showing that the kernel is shutting down."""
    expected_url = f"http://localhost:{port}/api/sessions/"
    method = response.request.method
    status_text = response.status_text

    if all(
        (
            response.url.startswith(expected_url),
            method == "DELETE",
            status_text == "No Content",
        )
    ):
        response.finished()
        return True
    return False


def is_saved(response: Response, name: str, port: int) -> bool:
    """Wait for the response showing that saving has taken place."""
    expected_url = f"http://localhost:{port}/api/contents/{name}"
    method = response.request.method
    try:
        t = response.json().get("type")
    except AttributeError:
        return False
    if all(
        (
            response.url.startswith(expected_url),
            t == "notebook",
            method == "PUT",
        )
    ):
        response.finished()
        return True
    return False


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


@pytest.fixture(scope="function")
def notebook(
    jupyter_server: t.Tuple[BrowserContext, Path, int],
) -> t.Callable:
    """Provide function-scoped fixture leveraging longer lived notebook."""
    context, tmp, port = jupyter_server
    path = tmp / f"notebook-{uuid4()}.ipynb"
    return lambda json_in: _notebook(
        json_in,
        context=context,
        port=port,
        nb=path,
    )


def _notebook(
    json_in: t.Dict[str, t.Any],
    context: BrowserContext,
    port: int,
    nb: Path,
) -> t.Dict[str, t.Any]:
    page = context.new_page()

    notebook_content = _base_notebook()
    cells = t.cast(t.List, notebook_content["cells"])
    cells.extend(json_in)
    notebook_content["cells"] = [make_cell(cell) for cell in cells]

    nb.write_text(json.dumps(notebook_content))
    url_base = f"http://localhost:{port}"

    name = nb.name
    url = f"{url_base}/notebooks/{name}"
    with page.expect_websocket(kernel_ready):
        page.goto(url)

    # Blank cells do not increment execution_count
    expected_count = sum(1 for cell in cells if cell["source"])

    run_menu = "#celllink"
    run_all_button = "text=Run All"

    page.click(run_menu)
    page.click(run_all_button)
    page.wait_for_selector(f"text=[{expected_count}]:", strict=True)

    with page.expect_response(lambda resp: is_saved(resp, name, port)) as resp:
        page.click('button[title="Save and Checkpoint"]')

    kernel_menu = "#kernellink"
    kernel_shutdown_button = "text=Shutdown"
    real_shutdown_button = 'button:has-text("Shutdown")'

    page.click(kernel_menu)
    page.click(kernel_shutdown_button)
    with page.expect_response(lambda resp: is_closing(resp, port)) as resp:
        page.click(real_shutdown_button)

    resp.value.finished()
    return json.loads(nb.read_text())


@pytest.fixture(scope="function")
def lab(
    jupyter_lab: t.Tuple[BrowserContext, Path, int],
) -> t.Callable:
    """Provide function-scoped fixture leveraging longer lived fixtures."""
    context, tmp, port = jupyter_lab
    path = tmp / f"notebook-{uuid4()}.ipynb"
    return lambda json_in: _lab(
        json_in,
        context=context,
        port=port,
        nb=path,
    )


def _lab(
    json_in: t.Dict[str, t.Any],
    context: BrowserContext,
    port: int,
    nb: Path,
) -> t.Dict[str, t.Any]:
    page = context.new_page()
    notebook_content = _base_notebook()

    cells = t.cast(t.List, notebook_content["cells"])
    cells.extend(json_in)
    notebook_content["cells"] = [make_cell(cell) for cell in cells]

    name = nb.name
    nb.write_text(json.dumps(notebook_content))
    url_base = f"http://localhost:{port}"

    url = f"{url_base}/lab/tree/{name}"
    with page.expect_websocket(kernel_ready):
        page.goto(url)

    # Blank cells do not increment execution_count
    expected_count = sum(1 for cell in cells if cell["source"])

    run_menu = "text=Run"
    run_all_button = 'ul[role="menu"] >> text=Run All Cells'

    page.click(run_menu)
    page.click(run_all_button)
    page.wait_for_selector(f"text=[{expected_count}]:", strict=True)

    with page.expect_response(lambda resp: is_saved(resp, name, port)) as resp:
        page.click("text=File")
        page.click('ul[role="menu"] >> text=Save Notebook')

    kernel_menu = "text=Kernel"
    shutdown_button = "text=Shut Down Kernel"

    page.click(kernel_menu)
    with page.expect_response(lambda resp: is_closing(resp, port)) as resp:
        page.click(shutdown_button)

    resp.value.finished()
    return json.loads(nb.read_text())


@pytest.fixture(scope="session")
def browser(headless: bool) -> t.Generator:
    """Provide a playwright browser for the entire session."""
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=headless)
        yield browser
        browser.close()


@pytest.fixture(scope="module")
def jupyter_server(
    browser: Browser,
    request: SubRequest,
    tmp_path_factory: TempPathFactory,
) -> t.Generator:
    """Fixture to run a notebook via Playwright.

    Seems like an actual browser is required for the JS to run, but headless
    Playwright seems to be working.
    """
    # Use different port for 3.7 vs 3.8  and lab vs notebook to allow parallel
    # tox runs
    port = sys.version_info[1] + 52750

    tmp = tmp_path_factory.getbasetemp()
    os.chdir(tmp)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "jupyter",
            "server",
            "--ServerApp.config_file=/dev/null",
            f"--ServerApp.port={port}",
            "--ServerApp.token=''",
            "--ServerApp.password=''",
            "--no-browser",
        ]
    )

    # Wait for jupyter server to be ready
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(("localhost", port))
        except (ConnectionRefusedError, OSError):
            continue
        else:
            break

    context = browser.new_context()
    page = context.new_page()

    url_base = f"http://localhost:{port}"
    with page.expect_response(
        lambda resp: "A Jupyter Server is running." in resp.text()
    ):
        page.goto(url_base)
    page.close()

    yield (context, tmp, port)
    context.close()
    proc.terminate()
    proc.wait(timeout=5)


@pytest.fixture(scope="module")
def jupyter_lab(
    browser: Browser,
    request: SubRequest,
    tmp_path_factory: TempPathFactory,
) -> t.Generator:
    """Fixture to run a notebook in jupyterlab via Playwright."""
    # Use different port for 3.7 vs 3.8  and lab vs notebook to allow parallel
    # tox runs
    port = sys.version_info[1] + 52740

    tmp = tmp_path_factory.getbasetemp()
    os.chdir(tmp)
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "jupyter",
            "lab",
            "--ServerApp.config_file=/dev/null",
            f"--ServerApp.port={port}",
            "--ServerApp.token=''",
            "--ServerApp.password=''",
            "--no-browser",
        ]
    )

    # Wait for jupyter server to be ready
    while True:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.connect(("localhost", port))
        except (ConnectionRefusedError, OSError):
            continue
        else:
            break

    context = browser.new_context()
    page = context.new_page()

    url_base = f"http://localhost:{port}/lab"

    while page.title() != "JupyterLab":
        page.goto(url_base)
    page.close()

    yield (context, tmp, port)
    context.close()
    proc.terminate()
    proc.wait(timeout=5)


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


def pytest_addoption(parser: Parser) -> None:
    """Add option to turn off headless (use headful) mode."""
    parser.addoption("--no-headless", action="store_true")


@pytest.fixture(scope="session")
def headless(pytestconfig: Config) -> bool:
    """Get the headless option."""
    return not pytestconfig.getoption("--no-headless")
