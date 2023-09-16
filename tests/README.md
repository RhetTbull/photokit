# PhotoKit Tests

## Running Tests

Tests are run with [pytest](https://docs.pytest.org/).
Tests must be run in order because single library mode tests must be run before multi-library tests
as once PhotoKit is in multi-library mode, single-library mode methods cannot be used. This is a
limitation of Apple's PhotoKit framwork.
