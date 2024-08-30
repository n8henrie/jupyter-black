"""Beautify jupyter cells using black."""

import logging
import typing as t

from IPython.core import getipython
from IPython.core.interactiveshell import ExecutionInfo
from IPython.terminal.interactiveshell import TerminalInteractiveShell as Ipt

import black

logging.basicConfig()
LOGGER = logging.getLogger("jupyter_black")

formatter = None


class BlackFormatter:
    """Formatter that stores config and call `black.format_cell`."""

    def __init__(
        self,
        ip: Ipt,
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
            black_config: Dictionary for black config options
        """
        self.shell = ip

        if black_config is None:
            black_config = {}

        mode_config = self._mode_config_from_pyproject_toml()

        tv = mode_config.pop("target_version", None)
        if tv is not None:
            versions = {black.TargetVersion[ver.upper()] for ver in tv}
            mode_config.update({"target_versions": versions})

        # Override with passed-in config
        mode_config.update(black_config)

        LOGGER.debug("config: %s", mode_config)
        mode = black.Mode(**mode_config)
        mode.is_ipynb = True
        self.mode = mode

    @staticmethod
    def _mode_config_from_pyproject_toml() -> t.Dict[str, t.Any]:
        """Return valid options for black.Mode from pyproject.toml."""
        toml_config = black.find_pyproject_toml((".",))
        if not toml_config:
            return {}

        LOGGER.debug("Using config from %s", toml_config)
        config = black.parse_pyproject_toml(toml_config)
        valid_options = set(t.get_type_hints(black.Mode))
        return {k: v for k, v in config.items() if k in valid_options}

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

        self.shell.set_next_input(formatted_code, replace=True)


def load_ipython_extension(
    ip: Ipt,
) -> None:
    """Load the extension via `%load_ext jupyter_black`.

    https://ipython.readthedocs.io/en/stable/config/extensions/#writing-extensions  # noqa
    """
    load(ip=ip)


def load(
    ip: t.Optional[Ipt] = None,
    line_length: t.Optional[int] = None,
    target_version: t.Optional[black.TargetVersion] = None,
    verbosity: t.Union[int, str] = logging.INFO,
    **black_config: t.Any,
) -> None:
    """Load the extension via `jupyter_black.load`.

    This allows passing in custom configuration.

    Arguments:
        ip: iPython interpreter -- you should be able to ignore this
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
        ip = getipython.get_ipython()  # type: ignore
    if not ip:
        return

    if line_length:
        black_config.update({"line_length": line_length})
    if target_version:
        black_config.update({"target_versions": set([target_version])})

    if formatter is None:
        formatter = BlackFormatter(ip, black_config=black_config)
    ip.events.register("pre_run_cell", formatter._format_cell)  # type: ignore


def unload_ipython_extension(ip: Ipt) -> None:
    """Unload the extension.

    https://ipython.readthedocs.io/en/stable/config/extensions/#writing-extensions
    """
    global formatter
    if formatter:
        ip.events.unregister(  # type: ignore
            "pre_run_cell", formatter._format_cell
        )
        formatter = None
