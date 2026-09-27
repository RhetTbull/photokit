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
>>> new_photo = pl.add_photo("/Users/user/Desktop/IMG_0632.JPG")
>>> new_photo.uuid
'8D35D987-9ECC-490C-811A-1AA33C8A7983'
>>> photo = pl.asset("CA2E3ADB-53A4-4E85-8D7D-4A664F970810")
>>> photo.original_filename
'IMG_4703.HEIC'
>>> photo.export("/private/tmp")
['/private/tmp/IMG_4703.heic']
>>> photo.revert()  # discard any edits
>>>
```

Libraries other than the system library can be opened by path; this switches PhotoKit to multi-library mode (see [Implementation Notes](#implementation-notes)):

```pycon
>>> from photokit import PhotoLibrary
>>> library2 = PhotoLibrary("/Users/user/Pictures/Test2.photoslibrary")
>>> library2.add_photo("/private/tmp/IMG_4703.HEIC")
<photokit.asset.PhotoAsset object at 0x...>
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

Python PhotoKit was originally developed on macOS Ventura (13.5.x) with initial testing on macOS Monterey (12.x) and macOS Sonoma (14.x). The test suite currently passes on macOS 27. No guarantees are made for other versions. It will not work on macOS Catalina (10.15.x) or earlier as those versions of macOS do not support some of the API calls used by this library.

## Implementation Notes

PhotoKit is a macOS framework for working with the Photos app. It is written in Objective-C and is not directly accessible from Python.  This project uses [pyobjc](https://github.com/ronaldoussoren/pyobjc) to provide a Python interface to the PhotoKit framework. It abstracts away the Objective-C implementation details and provides a Pythonic interface to the PhotoKit framework with Python classes to provide access to the user's Photo's library and assets in the library.

In addition the public PhotoKit API, this project uses private, undocumented APIs to allow access to arbitrary Photos libraries, accessing keywords, etc. The public PhotoKit API only allows access to the user's default Photos library (the so called "System Library") and limits the metadata available.

Opening a library other than the system library (`PhotoLibrary(library_path)` or `PhotoLibrary.enable_multi_library_mode()`) switches PhotoKit into multi-library mode for the rest of the process; after that, `PhotoLibrary()` (single-library mode) can no longer be used. Some methods (`smart_album()`, `smart_albums()`, `observe_changes()`) are only available in single-library mode.

A number of methods allow retrieval of assets of via a local identifier or [universally unique identifier](https://en.wikipedia.org/wiki/Universally_unique_identifier). Photos uses a local identifier to identify assets, albums, etc. within a single Photos library. The local identifier is specific to a given instance of the Photos library. The same asset in a different instance of the Photos library will have a different local identifier. This library uses the term "UUID" interchangeably with local identifier. A UUID is a string of hexadecimal digits that takes the form: `61A4B877-5EAC-4710-AA77-6D387629D9A5`. A local identifier returned by the native PhotoKit interface includes additional digits in the form `61A4B877-5EAC-4710-AA77-6D387629D9A5/L0/001`. For any method in this library that accepts a UUID, you may pass either the full local identifier or just the UUID portion. The library will automatically strip off the additional digits.

Whenever a public, documented method is available, the library uses that method. However, when no public method is available, this library uses private, undocumented methods to provide the functionality. If a private method cannot be found or does not work, the library uses direct access to the Photos database. If this doesn't work, the library will use AppleScript via the ScriptingBridge framework to access the Photos app. This is the least desirable method as it is slow and can be unreliable and only works on the current (default) Photos library.

### Editing Assets and AAE Files

Assets can be edited with `PhotoAsset.edit()`, including assets just added to the library, and edits can be undone with `PhotoAsset.revert()`. See [examples](examples/) for scripts that edit photos and videos with Core Image filters. For Live Photos, the edit callback may also return an edited paired video (this uses a private PhotoKit API); if it does not, Photos saves the edited version as a still photo. The `PhotoLibrary.add_*_with_adjustments()` methods add an original asset then apply an edited version along with adjustment data read from an AAE file (for example, one exported from Photos). Photos will not accept an edit from another process that uses its own adjustment format identifier, `com.apple.photo`; attempting to do so fails with `PHPhotosErrorDomain` error 3302. Adjustment data read from an AAE file with this identifier is therefore stored under a photokit-specific identifier. The adjustment data is preserved and the edited version displays normally (and "Revert to Original" works) but Photos treats the edit as coming from another app so it cannot re-open Apple's adjustments in its own editor.

It would be wonderful if Apple provided a full public API to Photos but this is unlikely to happen. The use of private APIs is not recommended by Apple and could break at any time. This library is provided as-is with no guarantees of functionality. Use at your own risk.

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
- [x] system_library_path()
- [x] default_library_path()
- [x] authorization_status()
- [ ] request_authorization() (*partially implemented, not well tested*)
- [ ] create_library() (*removed: the private API it used no longer works*)

#### Methods

- [x] library_path
- [x] is_system_library()
- [x] is_default_library()
- [x] assets() (all assets or `assets(uuids=[...])`)
- [x] asset()
- [x] albums()
- [x] album() (by UUID or title)
- [x] create_album()
- [x] delete_album()
- [x] smart_album(), smart_albums() (*single-library mode only*)
- [ ] moments()
- [ ] folders() (*stub: prints folders but does not return them*)
- [ ] create_folder()
- [x] fetch_burst_uuid() (*implemented, not yet tested*)
- [x] selection() (assets currently selected in Photos)
- [x] delete_assets()
- [x] add_photo()
- [x] add_video()
- [x] add_raw_pair_photo()
- [x] add_live_photo()
- [x] add_photo_with_adjustments()
- [x] add_video_with_adjustments()
- [x] add_live_photo_with_adjustments()
- [x] add_raw_pair_photo_with_adjustments()
- [x] create_keyword()
- [x] observe_changes(), stop_observing_changes() (*single-library mode only*)
- [x] \_\_len\_\_

### PhotoAsset

- [x] keywords getter/setter
- [x] isphoto
- [x] ismovie
- [x] isaudio
- [x] original_filename
- [x] uuid
- [x] local_identifier
- [x] raw_filename
- [x] hasadjustments
- [x] media_type
- [x] media_subtypes
- [x] favorite (getter/setter)
- [x] hidden (getter/setter)
- [x] panorama
- [x] hdr
- [x] screenshot
- [x] live
- [x] streamed
- [x] slow_mo
- [x] time_lapse
- [x] portrait
- [x] burst
- [x] burstid
- [x] source_type
- [x] pixel_width
- [x] pixel_height
- [x] date (created; setter/getter)
- [x] date_modified (setter/getter)
- [x] date_added (setter/getter)
- [x] timezone_offset (setter/getter)
- [x] timezone (setter/getter)
- [x] location (setter/getter)
- [x] duration
- [x] orientation() (current or original version)
- [x] title (getter/setter)
- [x] description (getter/setter)
- [x] edit
- [x] revert
- [ ] burst_photos
- [ ] export (implemented, not yet tested)

### VideoAsset

- [ ] export, including slow-mo videos (implemented, not yet tested)

### LivePhotoAsset

- [ ] export (implemented, not yet tested)

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

### Chores

- [ ] add doit for build automation
