# Developer Notes

These notes are for developers who want to contribute to the project and for me to remember how to do things.

## Building the project

PhotoKit uses [flit](https://flit.readthedocs.io/en/latest/) to build the project. To build the project, run the following command:

```bash
flit build
```

## Docs

Build docs with `mkdocs build` then deploy to GitHub pages with `mkdocs gh-deploy`

## Testing

Run tests with `pytest`.  The test suite will modify your system Photo's library but will delete all assets it creates when the test suite is complete. The test suite is interactive and needs to ask you to confirm some actions; it cannot be run unattended. See [tests/README.md](tests/README.md) for more information.

## Publishing to PyPI

Update version in `photokit/__init__.py` then run `flit build` followed by `flit publish`.
