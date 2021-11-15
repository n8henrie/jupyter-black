"""Beautify jupyter cells using black."""
import asyncio
import json
import logging
import threading
import typing as t
from contextlib import contextmanager
from queue import Queue
from textwrap import dedent

import black
from ipykernel.comm import Comm
from IPython.core import getipython
from IPython.core.interactiveshell import ExecutionInfo
from IPython.display import display, HTML, Javascript
from IPython.terminal.interactiveshell import TerminalInteractiveShell as Ipt

logging.basicConfig()
LOGGER = logging.getLogger("jupyter_black")

formatter = None


class BlackFormatter:
    """Formatter that stores config and call `black.format_cell`."""

    def __init__(
        self,
        ip: Ipt,
        _is_lab: bool = True,
        black_config: t.Optional[t.Dict[str, str]] = None,
    ) -> None:
        """Initialize the class with the passed in config.

        Notes on the JavaScript stuff for notebook:
            - Requires:
                - update=False for the `html` part
            - Doesn't seem to matter:
                - trailing semicolon
            - Other:
                - Can use `jb_cells.find` instead of the for loop if you set
                  the main function to `text/html` and set `raw=True`

            def display:
                https://github.com/ipython/ipython/blob/77e188547e5705a0e960551519a851ac45db8bfc/IPython/core/display_functions.py#L88  # noqa

        Arguments:
            ip: ipython shell
            is_lab: whether running in jupyterlab as opposed to ipython
                notebook
            black_config: Dictionary for black config options
        """
        self.shell = ip

        if black_config is None:
            black_config = {}

        config = self._config_from_pyproject_toml()

        tv = config.pop("target_version", None)
        if tv is not None:
            versions = {black.TargetVersion[ver.upper()] for ver in tv}
            config.update({"target_versions": versions})

        # Override with passed-in config
        config.update(black_config)
        LOGGER.debug(f"config: {config}")

        mode = black.Mode(**config)
        mode.is_ipynb = True
        self.mode = mode

        self.is_lab = True
        self.comm = Comm(target_name="jupyter_black", data={"foo": 0})
        self.comm.on_msg(self._set_lab_flag)

        ip.comm_manager.register_target(
            "jupyter_black", lambda comm, _: comm.on_msg(self._set_lab_flag)
        )
        js_func = """
            <script type="application/javascript" id="jupyter_black">
            (function(){
                if (typeof(Jupyter) === "undefined") {
                    return
                }
                kernel = Jupyter.notebook.kernel;
                kernel.comm_manager.register_target('jupyter_black',
                    function(comm, msg) {
                        comm.send({'jb_test_is_notebook': 1});
                    });
            })();
            function jb_set_cell(
                    jb_formatted_code
                    ) {
                for (var cell of Jupyter.notebook.get_cells()) {
                    if (cell.input_prompt_number == "*") {
                        cell.set_text(jb_formatted_code)
                        return
                    }
                }
            }
            </script>
            """
        display(
            HTML(js_func),
            display_id="jupyter_black",
            update=False,
        )

    @staticmethod
    def _config_from_pyproject_toml() -> t.Dict[str, t.Any]:
        toml_config = black.find_pyproject_toml((".",))
        if toml_config:
            LOGGER.debug(f"Using config from {toml_config}")
            return black.parse_pyproject_toml(toml_config)
        return {}

    def _set_cell(self, cell_content: str) -> None:
        if self.is_lab:
            self.shell.set_next_input(cell_content, replace=True)
        else:
            js_code = f"""
            (function() {{
                jb_set_cell({json.dumps(cell_content)})
            }})();
            """
            display(
                Javascript(js_code), display_id="jupyter_black", update=True
            )

    def _format_cell(self, cell_info: ExecutionInfo) -> None:
        if self.is_lab is None:
            self.is_lab = test_is_lab(self.shell)

        cell_content = str(cell_info.raw_cell)

        try:
            # `fast=False` seems to make *at most* a few ns difference even on
            # medium size cells and seems to help ensure correctness
            formatted_code = black.format_cell(
                cell_content, mode=self.mode, fast=False
            )
        except black.NothingChanged:
            return
        except Exception as e:
            LOGGER.debug(e)
            return

        self._set_cell(formatted_code)

    def _set_lab_flag(self, msg):
        print(f"got message: {msg}")
        LOGGER.warning(f"got message: {msg}")
        if msg["content"]["data"] == "jb_test_is_notebook":
            self.is_lab = False


@contextmanager
def hide_ipython_traceback(ip):
    """Hides the ipython traceback in a given context."""

    def hide_traceback(*_):
        pass

    savetb, ip._showtraceback = ip._showtraceback, hide_traceback
    try:
        yield
    finally:
        ip._showtraceback = savetb


def set_notebook_flag():
    """
    Ideas for how to automatically detect notebook vs lab.

    I don't really care for the `psutil` solution:
        https://discourse.jupyter.org/t/find-out-if-my-code-runs-inside-a-notebook-or-jupyter-lab/6935

    This seemed promising:
        https://jakevdp.github.io/blog/2013/06/01/ipython-notebook-javascrIpt-python-communication/

    Unfortunately, it doesn't seem that there is any way to access the results
    if this execution from this file, though after this runs you can access the
    variable `jb_test_is_notebook` from the notebook itself.

    Note that on first execution it might raise a notfounderror, but just rerun
    the cell and it should show up.
    """
    js_code = """
    <script type="application/javascript" id="jb_test_is_notebook">
    (function(){
        if (typeof(Jupyter) === "undefined") {
            return
        }
        var kernel = Jupyter.notebook.kernel;
        kernel.execute("jb_test_is_notebook = True");
    })();
    </script>
    """
    display(
        HTML(js_code),
        display_id="jb_test_is_notebook",
        update=False,
    )


def test_is_lab(ip: Ipt) -> bool:
    def raised_nameerror(ip: Ipt, q: Queue):
        """Put `False` onto `q` if there was a `NameError`.

        Tries to access `jb_test_is_notebook` in the environment, and re-raises
        if it is not found, which indicates that the JS above failed so set
        this (as a flag). The JS above relies on `Jupyter.notebook`, which is
        only found in the `notebook` environment (not lab), and so one would
        expect a `NameError` in lab and no error in notebook.

        `run_code` returns `True` for exceptions and `False` otherwise, so will
        reraise for `NameError`. It is a coroutine, so run with asyncio.

        See `run_code` at link below.

        https://ipython.readthedocs.io/en/stable/api/generated/IPython.core.interactiveshell.html#IPython.core.interactiveshell.InteractiveShell.run_code
        """
        code = ip.compile(
            dedent(
                """
        try:
            # Access the variable set via JS above
            jb_test_is_notebook
        except NameError:
            raise
        except:
            pass
        """
            ),
            "",
            "single",
        )
        result = asyncio.run(ip.run_code(code))
        q.put(result)

    q = Queue()

    # Jupyter has its own asyncio loop already running, which makes things very
    # difficult. Tried numerous variations of
    # `task = asyncio.get_running_loop().create_task(); while not task.done()`
    # without success. Threading seems to work fine.
    thread = threading.Thread(target=raised_nameerror, args=(ip, q))

    with hide_ipython_traceback(ip):
        thread.start()
        thread.join()

    had_nameerror = q.get()
    in_notebook = not had_nameerror
    return not in_notebook


def load_ipython_extension(
    ip: Ipt,
) -> None:
    """Load the extension via `%load_ext jupyter_black`.

    Usage examples:
        - `jupyter_black.load_ipython_extension(get_ipython())`
        - Lab only: `%load_ext jupyter_black`

    https://ipython.readthedocs.io/en/stable/config/extensions/#writing-extensions  # noqa
    """
    load(ip=ip)


def load(
    ip: t.Optional[Ipt] = None,
    lab: bool = True,
    line_length: t.Optional[int] = None,
    target_version: t.Optional[black.TargetVersion] = None,
    verbosity: t.Union[int, str] = logging.DEBUG,
    **black_config: t.Any,
) -> None:
    """Load the extension via `jupyter_black.load`.

    This allows passing in custom configuration.

    Arguments:
        ip: iPython interpreter -- you should be able to ignore this
        lab: Whether this is a jupyterlab session
        line_length: preferred line length
        target_version: preferred python version
        verbosity: logging verbosity
        **black_config: Other arguments you want to pass to black. See:
            https://github.com/psf/black/blob/911470a610e47d9da5ea938b0887c3df62819b85/src/black/mode.py#L99
    """
    global formatter
    global LOGGER
    LOGGER.setLevel(verbosity)

    if not ip:
        ip = getipython.get_ipython()
    if not ip:
        return

    if line_length:
        black_config.update({"line_length": line_length})
    if target_version:
        black_config.update({"target_versions": set([target_version])})

    if formatter is None:
        formatter = BlackFormatter(ip, _is_lab=lab, black_config=black_config)
    ip.events.register("pre_run_cell", formatter._format_cell)


def unload_ipython_extension(ip: Ipt) -> None:
    """Unload the extension.

    https://ipython.readthedocs.io/en/stable/config/extensions/#writing-extensions
    Usage examples:
        - `jupyter_black.unload_ipython_extension(get_ipython())`
        - Lab only: `%unload_ext jupyter_black`
    """
    global formatter
    if formatter:
        ip.events.unregister("pre_run_cell", formatter._format_cell)
        formatter = None


def unload(
    ip: t.Optional[Ipt] = None,
) -> None:
    """Unload the extension.

    Shortcut to the required `unload_ipython_extension` function.

    Usage: `jupyter_black.unload()`

    Arguments:
        ip: iPython interpreter -- you should be able to ignore this
    """
    if not ip:
        ip = getipython.get_ipython()
    if not ip:
        return
    unload_ipython_extension(ip)


def reload(
    ip: t.Optional[Ipt] = None,
) -> None:
    """Unload and then load the extension.

    Useful in case you get into an error state somehow.

    Usage examples:
        - `jupyter_black.reload()`

    `%reload_ext jupyter_black` should also work, but is not provided by this
    function.

    Arguments:
        ip: iPython interpreter -- you should be able to ignore this
    """
    if not ip:
        ip = getipython.get_ipython()
    if not ip:
        return
    unload(ip)
    load(ip)
