# [Changelog](https://keepachangelog.com)

## 0.3.2, 0.3.3 :: 2022-11-20

- Remove version constraints (thanks: @JakobGM, https://github.com/n8henrie/jupyter-black/issues/6)
- Update CI to ensure publishing should work

## 0.3.1 :: 2022-03-08

- Fix description (thanks: @bryanwweber)
- Version bump for PyPI

## 0.3.0 :: 2022-03-06

- Default to `lab=True`
    - Add warning popup for users that load in notebook with `lab=True`
      (including via `%load_ext`)
    - Fix tests for the above
    - Might as well minor version bump since this changes the API, even if
      still `0.x`

## 0.2.1 :: 20220-03-04

- Python 3.10 support
- Black 22 support

## 0.2.0 :: 2021-11-14

- Breaking change: default to `lab=True`; `%load_ext jupyter_black` will now
  work in jupyterlab and no longer work in a standalone notebook

## 0.1.1 :: 2021-09-28

- Unload the proper event

## 0.1.0 :: 2021-09-28

- First release on PyPI.
