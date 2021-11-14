"""Beautify jupyter cells using black."""
import json
import logging
import typing as t

import black
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
        is_lab: bool = True,
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

        self.is_lab = is_lab
        if is_lab:
            js_func = """
                <script type="application/javascript" id="jupyter_black">
                (function() {
                    if (window.IPython === undefined) {
                        return
                    }
                    var msg = "WARNING: it looks like you might have loaded " +
                        "jupyter_black in a non-lab notebook with " +
                        "`is_lab=True`. Please double check, and if " +
                        "loading with `%load_ext` please review the README!"
                    console.log(msg)
                    alert(msg)
                })()
                </script>
                """
        else:
            js_func = """
                <script type="application/javascript" id="jupyter_black">
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


def _test_is_lab() -> None:
    """
    Ideads for how to automatically detect notebook vs lab.

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
    (function(){
        var kernel = IPython.notebook.kernel;
        kernel.execute("jb_test_is_notebook = 1");
        console.log("I ran from javascrIpt");
    })();
    """
    display(Javascript(js_code))
    print("I ran from python")


def load_ipython_extension(
    ip: Ipt,
) -> None:
    """Load the extension via `%load_ext jupyter_black`.

    https://ipython.readthedocs.io/en/stable/config/extensions/#writing-extensions  # noqa
    """
    load(ip=ip)


def load(
    ip: t.Optional[Ipt] = None,
    lab: bool = True,
    line_length: t.Optional[int] = None,
    target_version: t.Optional[black.TargetVersion] = None,
    verbosity: t.Union[int, str] = logging.INFO,
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
        formatter = BlackFormatter(ip, is_lab=lab, black_config=black_config)
    ip.events.register("pre_run_cell", formatter._format_cell)


def unload_ipython_extension(ip: Ipt) -> None:
    """Unload the extension.

    https://ipython.readthedocs.io/en/stable/config/extensions/#writing-extensions
    """
    global formatter
    if formatter:
        ip.events.unregister("pre_run_cell", formatter._format_cell)
        formatter = None
