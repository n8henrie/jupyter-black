GREP := $(shell command -v ggrep || command -v grep)
SED := $(shell command -v gsed || command -v sed)

.PHONY: help
help:
	@awk '/^[^ ]*:/ { gsub(":.*", ""); print }' Makefile

.PHONY: clean
clean: clean-build clean-pyc clean-test

.PHONY: clean-build
clean-build:
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info
	rm -fr src/*.egg-info

.PHONY: clean-pyc
clean-pyc:
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

.PHONY: clean-test
clean-test:
	rm -fr .tox/

.PHONY: lint .venv
lint:
	./.venv/bin/python -m tox -e lint

.PHONY: test .venv
test:
	./.venv/bin/python -m tox -e py

.PHONY: test-all .venv
test-all:
	./.venv/bin/python -m tox --parallel

.PHONY: release .venv
release: dist
	./.venv/bin/python -m twine upload dist/*

dist: src/**/*.py pyproject.toml setup.cfg .venv
	./.venv/bin/python -m build
	ls -l dist

.venv:
	python3 -m venv .venv
	./.venv/bin/python -m pip install --upgrade pip

.PHONY: update-deps .venv
update-deps: requirements.txt
	@$(GREP) --invert-match --no-filename '^#' requirements*.txt | \
		$(SED) 's|==.*$$||g' | \
		xargs ./.venv/bin/python -m pip install --upgrade; \
	for reqfile in requirements*.txt; do \
		echo "Updating $${reqfile}..."; \
		./.venv/bin/python -c 'print("\n{:#^80}".format("  Updated reqs below  "))' >> "$${reqfile}"; \
		for lib in $$(./.venv/bin/pip freeze --all --isolated --quiet | $(GREP) '=='); do \
			if $(GREP) "^$${lib%%=*}==" "$${reqfile}" >/dev/null; then \
				echo "$${lib}" >> "$${reqfile}"; \
			fi; \
		done; \
	done;

.PHONY: test-debug .venv
test-debug:
	DEBUG=pw:api PWDEVBUG=console ./.venv/bin/python -m pytest -s
