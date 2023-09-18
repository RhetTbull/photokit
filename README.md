# Python PhotoKit

Python PhotoKit is a Python interface to the Apple [PhotoKit](https://developer.apple.com/documentation/photokit) framework for working with the Photos app on macOS.

This is currently a work in progress, and is not yet ready for use. I'm working on extracting the code from [osxphotos](https://github.com/RhetTbull/osxphotos) and adding additional functionality.

It is based on work done for [osxphotos](https://github.com/RhetTbull/osxphotos) which provides a command line interface to the Photos app on macOS as well as a python API for working with Photos.

## Synopsis

```pycon
>>> from photokit import PhotoLibrary
>>> PhotoLibrary.authorization_status()
(True, True)
>>> pl = PhotoLibrary()
>>> pl.add_photo("/Users/user/Desktop/IMG_0632.JPG")
'8D35D987-9ECC-490C-811A-1AA33C8A7983/L0/001'
>>> photo = pl.fetch_uuid("CA2E3ADB-53A4-4E85-8D7D-4A664F970810")
>>> photo.original_filename
'IMG_4703.HEIC'
>>> photo.export("/private/tmp")
['/private/tmp/IMG_4703.heic']
>>>
```

```pycon
>>> from photokit import PhotoLibrary
>>> new_library = PhotoLibrary.create_library("test.photoslibrary")
>>> new_library.add_photo("/private/tmp/IMG_4703.HEIC")
'07922E5C-5F4D-46C4-8DF9-D609FCF6714D/L0/001'
>>> library2 = PhotoLibrary("/Users/user/Pictures/Test2.photoslibrary")
```

## Installation

Still a work in progress and not yet ready for normal use. If you'd like to experiment with it, you can install it from GitHub:

```bash
git clone git@github.com:RhetTbull/photokit.git
cd photokit
python3 -m pip install flit
flit install
```

or via pip:

```bash
    pip3 install photokit
```

## Documentation

Documentation is available at [https://rhettbull.github.io/photokit/](https://rhettbull.github.io/photokit/).

## Supported Platforms

Python PhotoKit is being developed on macOS Ventura (13.5.x). Initial testing has been done on macOS Monterey (12.x) and macOS Sonoma (14.0 Developer Preview) and it appears to work though no guarantees are made. It will not work on macOS Catalina (10.15.x) or earlier as those versions of macOS do not support some of the API calls used by this library.

## Implementation Notes

PhotoKit is a macOS framework for working with the Photos app.  It is written in Objective-C and is not directly accessible from Python.  This project uses [pyobjc](https://github.com/ronaldoussoren/pyobjc) to provide a Python interface to the PhotoKit framework. It abstracts away the Objective-C implementation details and provides a Pythonic interface to the PhotoKit framework with Python classes to provide access to the user's Photo's library and assets in the library.

In addition the public PhotoKit API, this project uses private, undocumented APIs to allow access to arbitrary Photos libraries, creating new Photos libraries, accessing keywords, etc. The public PhotoKit API only allows access to the user's default Photos library (the so called "System Library") and limits the metadata available.

A number of methods allow retrieval of assets of via a local identifier or [universally unique identifier](https://en.wikipedia.org/wiki/Universally_unique_identifier). Photos uses a local identifier to identify assets, albums, etc. within a single Photos library. The local identifier is specific to a given instance of the Photos library. The same asset in a different instance of the Photos library will have a different local identifier. This library uses the term "UUID" interchangeably with local identifier. A UUID is a string of hexadecimal digits that takes the form: `61A4B877-5EAC-4710-AA77-6D387629D9A5`. A local identifier returned by the native PhotoKit interface includes additional digits in the form `61A4B877-5EAC-4710-AA77-6D387629D9A5/L0/001`. For any method in this library that accepts a UUID, you may pass either the full local identifier or just the UUID portion. The library will automatically strip off the additional digits.

## See Also

- [osxphotos](https://github.com/RhetTbull/osxphotos): Python app to export pictures and associated metadata from Apple Photos on macOS. Also includes a package to provide programmatic access to the Photos library, pictures, and metadata.
- [PhotoScript](https://github.com/RhetTbull/PhotoScript): Automate macOS Apple Photos app with python. Wraps AppleScript calls in Python to allow automation of Photos from Python code.

## License

This project is licensed under the terms of the MIT license.

## To Do

### PhotoLibrary

#### Static Methods

- [x] enable_multi_library_mode()
- [x] multi_library_mode()
- [x] system_photo_library_path()
- [x] authorization_status()
- [ ] request_authorization() (*partially implemented*)
- [x] create_library()

#### Methods

- [x] assets()
- [x] asset()
- [x] albums()
- [ ] smart_albums() (or method for each smart album, e.g. "recents()", "hidden()", etc.)?
- [ ] moments()
- [ ] folders()
- [x] fetch_uuid_list() (*rename to fetch_assets or use assets(uuid_list)*)
- [x] fetch_uuid() (*rename to fetch_asset() or asset()*)
- [ ] fetch_burst_uuid()
- [x] delete_assets()
- [x] add_photo()
- [ ] add_video()
- [ ] add_raw_pair()
- [ ] add_live_photo()
- [x] create_album()
- [ ] create_folder()
- [x] fetch_or_create_album() (renamed to album())
- [x] count(), __len__

### Asset

### PhotoAsset

### VideoAsset

### LivePhotoAsset

### Album

- [x] album properties
- [x] add_assets()
- [x] remove_assets()

### Folder

### PhotoDB

- [x] get_asset_uuids()
- [x] get_album_uuids

### Tests

- [x] initial test suite

### Documentation

- [x] initial documentation
- [x] publish to GitHub pages

### Type Hints/Linting

- [ ] mypy
- [ ] ruff
