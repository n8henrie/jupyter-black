# Contributing

Contributions are welcome, and they are greatly appreciated! Every little bit
helps, and credit will always be given.

You can contribute in many ways:

## Types of Contributions

### Report Bugs

Report bugs at <https://github.com/n8henrie/jupyter-black/issues>.

If you are reporting a bug, please include:

-  Your operating system name and version.
-  Any details about your local setup that might be helpful in
   troubleshooting.
-  Detailed steps to reproduce the bug.

### Fix Bugs

Look through the GitHub issues for bugs. Anything tagged with "bug" is open to
whoever wants to implement it.

### Implement Features

Look through the GitHub issues for features. Anything tagged with "feature" is
open to whoever wants to implement it.

### Write Documentation

jupyter-black could always use more documentation, whether as
part of the official jupyter-black docs, in docstrings, or
even on the web in blog posts, articles, and such.

### Submit Feedback

The best way to send feedback is to file an issue at
<https://github.com/n8henrie/jupyter-black/issues>.

If you are proposing a feature:

-   Explain in detail how it would work.
-   Keep the scope as narrow as possible, to make it easier to
    implement.
-   Remember that this is a volunteer-driven project, and that
    contributions are welcome :)

## Get Started!

Ready to contribute? Here's how to set up jupyter-black
for local development.

1. Fork the jupyter-black repo on GitHub.
1. Clone your fork locally:

        $ git clone git@github.com:your_name_here/jupyter-black.git
        $ cd jupyter-black

1. Check out the `dev` branch, where development happens prior to being merged
   into `master`. Your changes should be based on the `dev` branch, and your PR
   should eventually be requested against my `dev` branch.

        $ git checkout dev

1.  Install your local copy into a virtualenv (`venv` in modern python). Some
    linux distributions will require you to install `python-venv` or
    `python3-venv`, other times it will already be bundled with python. There
    are many ways to skin a cat, but this is how I usually set up a fork for
    local development:

        $ python3 -m venv .venv # set up hidden virtualenv folder: .venv
        $ source ./.venv/bin/actiate # activate virtualenv
        $ which python
        /Users/me/jupyter-black/.venv/bin/python
        $ python -m pip install -e .[test,dev] # editable install with dev deps

1. Create a branch for local development:

        $ git checkout -b name-of-your-bugfix-or-feature

    Now you can make your changes locally.

1. When you're done making changes, check that your changes pass any existing
   tests, including testing other Python versions with tox:

        $ tox

    To get flake8 and tox, just pip install them into your virtualenv.

1. Commit your changes and push your branch to GitHub:

        $ git add .
        $ git commit -m "Your detailed description of your changes."
        $ git push origin name-of-your-bugfix-or-feature

1. Submit a pull request through the GitHub website against my `dev` branch.

## Pull Request Guidelines

Before you submit a pull request, check that it meets these guidelines:

1. If the change is not *extremely* trivial, please start an issue for
   discussion **before** you do any work.
1. The pull request should include tests if I am using tests in the repo.
1. If the pull request adds functionality, the docs should be updated.
   Put your new functionality into a function with a docstring, and add
   the feature to the list in README.md
1. The pull request should generally work for the most recent version of
   Python3. If I have included CI file such as `.travis.yml` or
   `.github/workflows/*.yml` in the repo, ensure that the tests pass for all
   supported Python versions.

## Tips

To run a subset of tests: `pytest tests/test_your_test.py`
