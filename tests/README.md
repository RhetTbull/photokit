# PhotoKit Tests

## Running Tests

Tests are run with [pytest](https://docs.pytest.org/).

Tests must be run in order because single library mode tests must be run before multi-library tests
as once PhotoKit is in multi-library mode, single-library mode methods cannot be used. This is a
limitation of Apple's PhotoKit framwork. The test files are named such that pytest will run them in the right order.

Also, some tests are interactive and will prompt you for input (for example, the number of photos and videos in your Photos library) as this input is used to test PhotoKit.

## Test Assets

The test suite includes a number of images and videos used as test assets. These assets are copyright Rhet Turnbull, 2023, and licensed under the Creative Commons Attribution 4.0 International Public License.
