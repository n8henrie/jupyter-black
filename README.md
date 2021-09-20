# jupyter-black

master: [![master branch build status](https://github.com/n8henrie/jupyter-black/actions/workflows/python-package.yml/badge.svg?branch=master)](https://github.com/n8henrie/jupyter-black/actions/workflows/python-package.yml)
<!-- dev: [![dev branch build status](https://github.com/n8henrie/jupyter-black/actions/workflows/python-package.yml/badge.svg?branch=dev)](https://github.com/n8henrie/jupyter-black/actions/workflows/python-package.yml) -->

A simple extension for Jupyter Notebook and Jupyter Lab to beautify Python code
automatically using Black. Fork of
[dnanhkhoa/nb_black](https://github.com/dnanhkhoa/nb_black) with a few minor
modifications:

## Features

Once loaded, automatically format syntactically correct `jupyter` cells with
`black` once then are run.

Enhancements compared to [dnanhkhoa/nb_black](https://github.com/dnanhkhoa/nb_black):

- Configurability:
    - Try to read black config from `pyproject.toml` if available
    - Override settings such as line length and black.TargetVersion if desired

- Free software: MIT

## Introduction

[`black`][black] is an extremely popular python formatter. [Jupyter][jupyter] is an
awesome way to run python. This extension helps you automatically `black`en
your `jupyter`.

## Dependencies

- Python >= 3.7
- See `setup.cfg`

## Quickstart

```
python3 -m venv .venv && source ./.venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install jupyter-black jupyter
python3 -m jupyter notebook
```

From here, there are two ways to load the extension:

### Configurable (recommended):

```python
import jupyter_black

jupyter_black.load()
```

To look at configuration options:

```python
jupyter_black.load??
```

For example:

```python
import black
import jupyter_black

jupyter_black.load(
    lab=False,
    line_length=79,
    verbosity="DEBUG",
    target_version=black.TargetVersion.PY39,
)
```

### The other way:

```python
%load_ext jupyter_black
```

This will load the extension using your defaults from `pyproject.toml` if
available, or use the `black` defaults.

### Development Setup

1. Clone the repo: `git clone https://github.com/n8henrie/jupyter-black && cd
   jupyter-black`
2. Make a virtualenv: `python3 -m venv .venv`
3. Activate venv, update pip, and install editable test/dev version:

```console
$ source ./.venv/bin/activate
$ ./.venv/bin/python -m pip install --upgrade pip
$ ./.venv/bin/python -m pip install -e .[test,dev]
```

Notes:

- Tests use [playwright][playwright]
    - You'll need to run these commands to run the tests:
        - `python -m playwright install firefox`
        - `python -m playwright install-deps firefox`
- `tox` will automatically run these installation steps (helpful for CI).

## TODO

Contribution ideas:

- [ ] More tests, currently very basic
    - Ensure config is overridden in unsurprising ways
    - Ensure other config options are properly passed to `black`
    - Ensure that `pyproject.toml` is searched for properly
- [ ] Write tests for jupyter lab, currently only tested for notebook
    - I think the fixture could easily be modularized to also work for `lab`,
      but haven't done the work yet.

## Contributing

Please see `CONTRIBUTING.md` and `TODO`.

## Troubleshooting / FAQ

- How can I install an older / specific version of [jupyter black](jupyter-black)?
    - Install from a tag:
        - pip install git+git://github.com/n8henrie/jupyter-black.git@v0.1.0
    - Install from a specific commit:
        - pip install git+git://github.com/n8henrie/jupyter-black.git@aabc123def456ghi789


[black]: https://github.com/psf/black
[jupyter]: https://jupyter.org/
[playwright]: https://playwright.dev/python/


## Acknowledgements

Many thanks to [dnanhkhoa/nb_black](https://github.com/dnanhkhoa/nb_black) for
the original version!

And of course many thanks to the [black][black] and [jupyter][jupyter] teams.

## Buy Me a Coffee

[☕️](https://n8henrie.com/donate)
