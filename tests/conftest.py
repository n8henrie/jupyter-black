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

from _pytest.config import Config
from _pytest.config.argparsing import (
    Parser,
)
from _pytest.fixtures import SubRequest

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Dialog,
    Response,
    TimeoutError,
    WebSocket,
    sync_playwright,
)
from playwright.sync_api import (
    Error as PWError,
)

import pytest
from pytest import TempPathFactory


def decode_event(data: t.Union[bytes, str]) -> t.Dict:
    r"""Decode an event of bytes into a dictionary.

    Previously a simple `json.loads` was fine, but it appears that jupyterlab
    4.0 has changed things and now there is a hash prefixed to ensure integrity
    of the message. Instead of going through the trouble of properly decoding
    (I think the process is described in the document below as of 20240107),
    because this is only necessary as a sign that the kernel is ready to run
    the tests, we'll take a few shortcuts.

    Additionally, previously the decoded data was a single dict with multiple
    layers, whereas the new protocol has 4 separate objects; this function
    combines then in such a way as to retain compatibility.

    Feel free to contribute a better process if you have one.

    https://jupyter-client.readthedocs.io/en/latest/messaging.html#the-wire-protocol

    An example message, which hopefully isn't revealing all my credit card
    information:

    ```
    b'\x06\x00\x00\x00\x00\x00\x00\x008\x00\x00\x00\x00\x00\x00\x00=\x00\x00\x00\x00\x00\x00\x00\x0b\x01\x00\x00\x00\x00\x00\x00\xec\x01\x00\x00\x00\x00\x00\x00\xee\x01\x00\x00\x00\x00\x00\x00\t\x02\x00\x00\x00\x00\x00\x00iopub{"msg_id": "9148ee59-f8f0f2fd901f7456b0940f74_75282_8", "msg_type": "status", "username": "n8henrie", "session": "9148ee59-f8f0f2fd901f7456b0940f74", "date": "2024-01-07T17:07:26.528988Z", "version": "5.3"}{"msg_id": "cd68eda6-6b55-408f-83c6-57c104d2bab6_75204_1", "msg_type": "kernel_info_request", "username": "n8henrie", "session": "cd68eda6-6b55-408f-83c6-57c104d2bab6", "date": "2024-01-07T17:07:26.525729Z", "version": "5.3"}{}{"execution_state": "idle"}'  # noqa
    ```
    """
    if isinstance(data, str):
        return json.loads(data)

    event_start = data.find(b'{"')
    trimmed = data[event_start:]

    decoder = json.JSONDecoder()

    dicts = []
    chunk = trimmed.decode("utf8")
    while chunk:
        dict_, chunk_start = decoder.raw_decode(chunk)
        dicts.append(dict_)
        chunk = chunk[chunk_start:]

    (
        header,
        _parent,
        _metadata,
        content,
    ) = dicts
    header["content"] = content
    return header


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
                "codemirror_mode": {
                    "name": "ipython",
                    "version": 3,
                },
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


def all_cells_run(
    data: t.Union[bytes, str],
    expected_count: int,
) -> bool:
    """Wait for an event signaling all cells have run.

    `execution_count` should equal number of nonempty cells.
    """
    event = decode_event(data)
    try:
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


def is_saved(
    response: Response,
    name: str,
    port: int,
) -> bool:
    """Wait for the response showing that saving has taken place."""
    expected_url = f"http://localhost:{port}/api/contents/{name}"
    method = response.request.method
    try:
        response_type = response.json().get("type")
    except AttributeError:
        return False
    if all(
        (
            response.url.startswith(expected_url),
            response_type == "notebook",
            method == "PUT",
        )
    ):
        response.finished()
        return True
    return False


def kernel_ready_event(data: t.Union[bytes, str]) -> bool:
    """Wait for an event signaling the kernel is ready to run cell.

    Seems like `comm_info_reply` is a reasonable target for `jupyter notebook`
    whereas `kernel_info_reply` works for `jupyter server`.
    """
    event = decode_event(data)
    try:
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
    with ws.expect_event(
        "framereceived",
        kernel_ready_event,
    ):
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

    # This will raise a TimeoutError when the alert is presented, since the
    # `wait_for_selector` will never happen. Raising our own error here doesn't
    # work due to https://github.com/microsoft/playwright-python/issues/1017
    def close_on_dialog(
        dialog: Dialog,
    ) -> None:
        if dialog.message.startswith("WARNING:"):
            page.close()
        else:
            dialog.dismiss()

    page.on("dialog", close_on_dialog)

    page.click("text=Run")
    page.locator("#jp-mainmenu-run").get_by_text(
        "Run All Cells", exact=True
    ).click()
    page.wait_for_selector(
        f"text=[{expected_count}]:",
        strict=True,
    )

    with page.expect_response(lambda resp: is_saved(resp, name, port)) as resp:
        page.get_by_text("File", exact=True).click()
        page.get_by_text("Save All").click()

    page.get_by_text("Kernel", exact=True).click()
    with page.expect_response(lambda resp: is_closing(resp, port)) as resp:
        page.get_by_text("Shut Down Kernel").click()

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

    page.click("text=Run")

    for run_menu in [
        'ul[role="menu"]',
        "#jp-mainmenu-run",  # jupyterlab 4
    ]:
        run_all_button = page.locator(run_menu).get_by_text(
            "Run All Cells", exact=True
        )
        if run_all_button.count() == 1:
            run_all_button.click()

    page.wait_for_selector(
        f"text=[{expected_count}]:",
        strict=True,
    )

    with page.expect_response(lambda resp: is_saved(resp, name, port)) as resp:
        page.get_by_text("File", exact=True).click()
        page.get_by_text("Save All").click()

    kernel_menu = "text=Kernel"
    shutdown_button = "text=Shut Down Kernel"

    page.click(kernel_menu)
    with page.expect_response(lambda resp: is_closing(resp, port)) as resp:
        page.click(shutdown_button)

    resp.value.finished()
    return json.loads(nb.read_text())


@pytest.fixture(scope="session")
def browser(
    headless: bool,
) -> t.Generator:
    """Provide a playwright browser for the entire session."""
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=headless)
        yield browser
        browser.close()


def _wait_for_server(browser: Browser, port: int) -> None:
    # Wait for jupyter server to be ready
    while True:
        try:
            with socket.socket(
                socket.AF_INET,
                socket.SOCK_STREAM,
            ) as sock:
                sock.connect(("localhost", port))
        except (
            ConnectionRefusedError,
            OSError,
        ):
            continue
        else:
            break

    err = None
    for _ in range(20):
        page = browser.new_page()
        try:
            with page.expect_response(
                lambda resp: resp.json().get("version") is not None,
                timeout=500,
            ):
                page.goto(f"http://localhost:{port}/api")
        except TimeoutError:
            continue
        except PWError as e:
            err = e
            if not e.message.startswith("NS_ERROR_CONNECTION_REFUSED"):
                raise
            continue
        else:
            return
        finally:
            page.close()
    else:
        if err:
            raise err
        raise Exception("Unable to get the server started")


@pytest.fixture(scope="module")
def jupyter_server(
    request: SubRequest,
    browser: Browser,
    tmp_path_factory: TempPathFactory,
    open_port: int,
) -> t.Tuple[BrowserContext, Path, int]:
    """Fixture to run a notebook via Playwright.

    Seems like an actual browser is required for the JS to run, but headless
    Playwright seems to be working.
    """
    port = open_port
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
            "--ServerApp.port_retries=0",
            "--ServerApp.token=''",
            "--ServerApp.password=''",
            "--no-browser",
        ]
    )
    context = browser.new_context()

    def teardown() -> None:
        context.close()
        proc.terminate()
        proc.wait(timeout=5)

    request.addfinalizer(teardown)

    _wait_for_server(
        browser,
        port=port,
    )
    return (context, tmp, port)


@pytest.fixture(scope="module")
def open_port() -> int:
    """Find an open port."""
    with socket.socket() as s:
        s.bind(("", 0))
        port = s.getsockname()[1]
    return port


@pytest.fixture(scope="module")
def jupyter_lab(
    request: SubRequest,
    browser: Browser,
    tmp_path_factory: TempPathFactory,
    open_port: int,
) -> t.Tuple[BrowserContext, Path, int]:
    """Fixture to run a notebook in jupyterlab via Playwright."""
    port = open_port
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
            "--ServerApp.port_retries=0",
            "--ServerApp.token=''",
            "--ServerApp.password=''",
            "--no-browser",
        ]
    )
    context = browser.new_context()

    def teardown() -> None:
        context.close()
        proc.terminate()
        proc.wait(timeout=10)

    request.addfinalizer(teardown)

    _wait_for_server(
        browser,
        port=port,
    )

    return (context, tmp, port)


def source_from_cell(
    content: t.Dict[str, t.Any],
    cell_id: str,
) -> str:
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


def pytest_addoption(
    parser: Parser,
) -> None:
    """Add option to turn off headless (use headful) mode."""
    parser.addoption(
        "--no-headless",
        action="store_true",
    )


@pytest.fixture(scope="session")
def headless(
    pytestconfig: Config,
) -> bool:
    """Get the headless option."""
    return not pytestconfig.getoption("--no-headless")
