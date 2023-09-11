# PhotoKit

A python interface to the Apple [PhotoKit](https://developer.apple.com/documentation/photokit) framework for working with the Photos app on macOS.

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

Still a work in progress and not yet ready for normal use. It is not yet hosted on PyPI. If you'd like to experiment with it, you can install it from GitHub:

```bash
git clone git@github.com:RhetTbull/photokit.git
cd photokit
python3 -m pip install flit
flit install
```

## Implementation Notes

PhotoKit is a macOS framework for working with the Photos app.  It is written in Objective-C and is not directly accessible from Python.  This project uses [pyobjc](https://github.com/ronaldoussoren/pyobjc) to provide a Python interface to the PhotoKit framework. It abstracts away the Objective-C implementation details and provides a Pythonic interface to the PhotoKit framework with Python classes to provide access to the user's Photo's library and assets in the library.

In addition the public PhotoKit API, this project uses private, undocumented APIs to allow access to arbitrary Photos libraries, creating new Photos libraries, etc. The public PhotoKit API only allows access to the user's default Photos library (the so called "System Library").

## See Also

- [osxphotos](https://github.com/RhetTbull/osxphotos): Python app to export pictures and associated metadata from Apple Photos on macOS. Also includes a package to provide programmatic access to the Photos library, pictures, and metadata.
- [PhotoScript](https://github.com/RhetTbull/PhotoScript): Automate macOS Apple Photos app with python. Wraps AppleScript calls in Python to allow automation of Photos from Python code.

## License

This project is licensed under the terms of the MIT license.

## To Do

### PhotoLibrary

#### Static Methods

- [x] enable_multi_library_mode():
- [x] multi_library_mode() -> bool:
- [x] system_photo_library_path() -> str:
- [x] authorization_status() -> tuple[bool, bool]:
- [ ] request_authorization(): (partially implemented)
- [x] create_library(library_path: str | pathlib.Path | os.PathLike) -> PhotoLibrary:

#### Methods

- [x] assets(self) -> list[Asset]:
- [ ] albums(self, top_level: bool = False) -> list[Album]:
-- Done for single library mode, need to implement for multi-library mode
- [ ] folders(self):
- [x] fetch_uuid_list(self, uuid_list):
- [x] fetch_uuid(self, uuid):
- [ ] fetch_burst_uuid(self, burstid, all=False):
- [ ]delete_assets(self, photoassets: list[PhotoAsset]):
- [x] add_photo(self, image_path: str | pathlib.Path | os.PathLike):
- [ ] add_video(self, video_path: str | pathlib.Path | os.PathLike):
- [ ] add_raw(self, raw_path: str | pathlib.Path | os.PathLike):
- [ ] add_live_photo(self, live_photo_path: str | pathlib.Path | os.PathLike):

### Asset

### PhotoAsset

### VideoAsset

### LivePhotoAsset

### Album

### Folder

### Tests
