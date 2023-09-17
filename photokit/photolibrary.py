"""PhotoLibrary class for photokit"""

from __future__ import annotations

import os
import pathlib
import threading

import objc
import Photos
from Foundation import NSURL, NSString
from wurlitzer import pipes

from .album import Album
from .asset import Asset, LivePhotoAsset, PhotoAsset, VideoAsset
from .constants import PHAccessLevelAddOnly, PHAccessLevelReadWrite
from .exceptions import (
    PhotoKitAlbumCreateError,
    PhotoKitAlbumDeleteError,
    PhotoKitAuthError,
    PhotoKitCreateLibraryError,
    PhotoKitError,
    PhotoKitFetchFailed,
    PhotoKitImportError,
    PhotoKitMediaTypeError,
)
from .objc_utils import NSURL_to_path
from .photosdb import PhotosDB
from .platform import get_macos_version

# global to hold state of single/multi library mode
# once a multi-library mode API is used, the same process cannot use single-library mode APIs again
_global_single_library_mode = True

# TODO: burst: includeAllBurstAssets
# https://developer.apple.com/documentation/photokit/phfetchoptions/1624786-includeallburstassets?language=objc


class PhotoLibrary:
    """Interface to PhotoKit PHImageManager and PHPhotoLibrary"""

    def __init__(self, library_path: str | None = None):
        """Initialize ImageManager instance.  Requests authorization to use the
        Photos library if authorization has not already been granted.

        Args:
            library_path: str, path to Photos library to use; if None, uses default shared library

        Raises:
            PhotoKitAuthError if unable to authorize access to PhotoKit
            PhotoKitError if attempt to call single-library mode API after multi-library mode API

        Note:
            Access to the default shared library is provided via documented PhotoKit APIs.
            Access to other libraries via library_path is provided via undocumented private PhotoKit APIs.
            Thus this may break at any time.
        """

        # check authorization status
        auth_status = PhotoLibrary.authorization_status()
        if True not in auth_status:
            raise PhotoKitAuthError(f"Unable to access Photos library: {auth_status}")

        # if library_path is None, use default shared library
        global _global_single_library_mode
        if not library_path:
            if not _global_single_library_mode:
                # cannot use single-library mode APIs again after using multi-library mode APIs
                raise PhotoKitError(
                    "Cannot use single-library mode APIs after using multi-library mode APIs"
                )
            _global_single_library_mode = True
            self._phimagemanager = Photos.PHCachingImageManager.defaultManager()
            self._phphotolibrary = Photos.PHPhotoLibrary.sharedPhotoLibrary()
            self._photosdb = PhotosDB(PhotoLibrary.system_photo_library_path())
        else:
            # undocumented private API to get PHPhotoLibrary for a specific library
            Photos.PHPhotoLibrary.enableMultiLibraryMode()
            _global_single_library_mode = False
            self._phphotolibrary = (
                Photos.PHPhotoLibrary.alloc().initWithPhotoLibraryURL_type_(
                    NSURL.fileURLWithPath_(library_path), 0
                )
            )
            self._phimagemanager = Photos.PHImageManager.alloc().init()
            self._photosdb = PhotosDB(library_path)

    @staticmethod
    def enable_multi_library_mode():
        """Enable multi-library mode.  This is a no-op if already enabled.

        Note:
            Some PhotoKit APIs only work in multi-library mode.
            Once enabled, it cannot be disabled and only single-library mode APIs will work.
            In practice, you should not need to use this and PhotoLibrary will manage this automatically.
        """
        Photos.PHPhotoLibrary.enableMultiLibraryMode()
        global _global_single_library_mode
        _global_single_library_mode = False

    @staticmethod
    def multi_library_mode() -> bool:
        """Return True if multi-library mode is enabled, False otherwise"""
        return not _global_single_library_mode

    @staticmethod
    def system_photo_library_path() -> str:
        """Return path to system photo library"""
        return NSURL_to_path(Photos.PHPhotoLibrary.systemPhotoLibraryURL())

    @staticmethod
    def authorization_status() -> tuple[bool, bool]:
        """Get authorization status to use user's Photos Library

        Returns: tuple of bool for (read_write, add_only) authorization status
        """

        (ver, major, _) = get_macos_version()
        if (int(ver), int(major)) < (10, 16):
            auth_status = Photos.PHPhotoLibrary.authorizationStatus()
            if auth_status == Photos.PHAuthorizationStatusAuthorized:
                return (True, True)
            return (False, False)

        # requestAuthorization deprecated in 10.16/11.0
        # use requestAuthorizationForAccessLevel instead
        # ref: https://developer.apple.com/documentation/photokit/phphotolibrary/3616052-authorizationstatusforaccessleve?language=objc
        read_write = Photos.PHPhotoLibrary.authorizationStatusForAccessLevel_(
            PHAccessLevelReadWrite
        )
        add_only = Photos.PHPhotoLibrary.authorizationStatusForAccessLevel_(
            PHAccessLevelAddOnly
        )
        return (
            read_write == Photos.PHAuthorizationStatusAuthorized,
            add_only == Photos.PHAuthorizationStatusAuthorized,
        )

    @staticmethod
    def request_authorization(
        access_level: int = PHAccessLevelReadWrite,
    ):
        """Request authorization to user's Photos Library

        Args:
            access_level: (int) PHAccessLevelAddOnly or PHAccessLevelReadWrite

        Returns: True if authorization granted, False otherwise

        Note: In actual practice, the terminal process running the python code
            will do the actual request. This method exists for use in bundled apps
            created with py2app, etc.  It has not yet been well tested.
        """

        def handler(status):
            pass

        read_write, add_only = PhotoLibrary.authorization_status()
        if (
            access_level == PHAccessLevelReadWrite
            and read_write
            or access_level == PHAccessLevelAddOnly
            and add_only
        ):
            # already have access
            return True

        (ver, major, _) = get_macos_version()
        if (int(ver), int(major)) < (10, 16):
            # it seems the first try fails after Terminal prompts user for access so try again
            for _ in range(2):
                Photos.PHPhotoLibrary.requestAuthorization_(handler)
                auth_status = Photos.PHPhotoLibrary.authorizationStatus()
                if auth_status == Photos.PHAuthorizationStatusAuthorized:
                    break
            return bool(auth_status)

        # requestAuthorization deprecated in 10.16/11.0
        # use requestAuthorizationForAccessLevel instead
        for _ in range(2):
            auth_status = (
                Photos.PHPhotoLibrary.requestAuthorizationForAccessLevel_handler_(
                    access_level, handler
                )
            )
            read_write, add_only = PhotoLibrary.authorization_status()
            if (
                access_level == PHAccessLevelReadWrite
                and read_write
                or access_level == PHAccessLevelAddOnly
                and add_only
            ):
                return True
        return bool(auth_status)

    @staticmethod
    def create_library(library_path: str | pathlib.Path | os.PathLike) -> PhotoLibrary:
        """Create a new Photos library at library_path

        Args:
            library_path: str or pathlib.Path, path to new library

        Returns: PhotoLibrary object for new library

        Raises:
            FileExistsError if library already exists at library_path
            PhotoKitCreateLibraryError if unable to create library

        Note:
            This only works in multi-library mode; multi-library mode will be enabled if not already enabled.
            This may file (after a long timeout) if a library with same name was recently created
            (even if it has since been deleted).
        """
        library_path = (
            str(library_path) if not isinstance(library_path, str) else library_path
        )
        if pathlib.Path(library_path).is_dir():
            raise FileExistsError(f"Library already exists at {library_path}")

        # This only works in multi-library mode
        PhotoLibrary.enable_multi_library_mode()

        # Sometimes this can generate error messages to stderr regarding CoreData XPC errors
        # I have not yet figured out what causes this
        # Suppress the errors with pipes() and raise error when it times out
        # Error appears to occur if a library with same name was recently created (even if it has since been deleted)
        with pipes() as (out, err):
            photo_library = Photos.PHPhotoLibrary.alloc().initWithPhotoLibraryURL_type_(
                NSURL.fileURLWithPath_(library_path), 0
            )
            if photo_library.createPhotoLibraryUsingOptions_error_(None, None):
                return PhotoLibrary(library_path)
            else:
                raise PhotoKitCreateLibraryError(
                    f"Unable to create library at {library_path}"
                )

    def library_path(self) -> str:
        """Return path to Photos library"""
        return NSURL_to_path(self._phphotolibrary.photoLibraryURL())

    def assets(self, uuids: list[str] | None = None) -> list[Asset]:
        """Return list of all assets in the library or subset filtered by UUID.

        Args:
            uuids: (list[str]) UUID of image assets to fetch; if None, fetch all assets

        Returns: list of Asset objects

        Note: Does not currently return assets that are hidden or in trash nor non-selected burst assets
        """
        if uuids:
            return self._assets_from_uuid_list(uuids)

        if PhotoLibrary.multi_library_mode():
            asset_uuids = self._photosdb.get_asset_uuids()
            return self._assets_from_uuid_list(asset_uuids)

        with objc.autorelease_pool():
            options = Photos.PHFetchOptions.alloc().init()
            # options.setIncludeHiddenAssets_(True)
            # TODO: to access hidden photos, Photos > Settings > General > Privacy > Use Touch ID or Password
            # must be turned off
            # print(options.includeHiddenAssets())
            assets = Photos.PHAsset.fetchAssetsWithOptions_(options)
            asset_list = [assets.objectAtIndex_(idx) for idx in range(assets.count())]
            return [self._asset_factory(asset) for asset in asset_list]

    def albums(self, top_level: bool = False) -> list[Album]:
        """Return list of albums in the library

        Args:
            top_level: if True, return only top level albums

        Returns: list of Album objects
        """
        if PhotoLibrary.multi_library_mode():
            album_uuids = self._photosdb.get_album_uuids(top_level=top_level)
            return self._albums_from_uuid_list(album_uuids)

        with objc.autorelease_pool():
            # these are single library mode only
            # this gets all user albums
            if top_level:
                # this gets top level albums but also folders (PHCollectionList)
                albums = (
                    Photos.PHCollectionList.fetchTopLevelUserCollectionsWithOptions_(
                        None
                    )
                )
            else:
                albums = Photos.PHAssetCollection.fetchAssetCollectionsWithType_subtype_options_(
                    Photos.PHAssetCollectionTypeAlbum,
                    Photos.PHAssetCollectionSubtypeAny,
                    None,
                )

            album_list = []
            for i in range(albums.count()):
                album = albums.objectAtIndex_(i)
                # filter out PHCollectionList (folders), PHCloudSharedAlbum (shared albums)
                if not isinstance(
                    album, (Photos.PHCollectionList, Photos.PHCloudSharedAlbum)
                ):
                    album_list.append(album)
            return [Album(self, album) for album in album_list]

    def album(self, uuid: str | None = None, title: str | None = None) -> Album:
        """Get Album by UUID or name

        Args:
            uuid: str | None; UUID of album to fetch
            title: str | None; title/name of album to fetch

        Returns: Album object

        Raises:
            PhotoKitFetchFailed if fetch failed (album not found)
            ValueError if both uuid and title are None or both are not None

        Note: You must pass only one of uuid or title, not both. If more than one album has the same title,
        the behavior is undefined; one of the albums will be returned but no guarantee is made as to which one.
        """

        if not (uuid or title) or (uuid and title):
            raise ValueError(
                f"Must pass either uuid or title but not both: {uuid=}, {title=}"
            )

        if uuid:
            try:
                result = self._albums_from_uuid_list([uuid])
                return result[0]
            except Exception as e:
                raise PhotoKitFetchFailed(
                    f"Fetch did not return result for uuid {uuid}: {e}"
                )

        if title:
            albums = self.albums()
            for album in albums:
                if album.title == title:
                    return album
            raise PhotoKitFetchFailed(f"Fetch did not return result for title {title}")

    def create_album(self, title: str) -> Album:
        """Create a new album in the library

        Args:
            title: str, title of new album

        Returns: Album object for new album

        Raises:
            PhotoKitAlbumCreateError if unable to create album
        """

        with objc.autorelease_pool():
            event = threading.Event()

            # Create a new album
            def completion_handler(success, error):
                if error:
                    raise PhotoKitAlbumCreateError(
                        f"Error creating album {title}: {error}"
                    )
                event.set()

            album_uuid = None

            def create_album_handler(title):
                nonlocal album_uuid

                creation_request = Photos.PHAssetCollectionChangeRequest.creationRequestForAssetCollectionWithTitle_(
                    title
                )

                album_uuid = (
                    creation_request.placeholderForCreatedAssetCollection().localIdentifier()
                )

            self._phphotolibrary.performChanges_completionHandler_(
                lambda: create_album_handler(title), completion_handler
            )

            event.wait()

            return self.album(album_uuid)

    def delete_album(self, album: Album):
        """Delete album in the library

        Args:
            album: Album object to delete

        Raises:
            PhotoKitAlbumDeleteError if unable to create album
        """

        with objc.autorelease_pool():
            event = threading.Event()

            def completion_handler(success, error):
                if error:
                    raise PhotoKitAlbumDeleteError(
                        f"Error deleting album {album}: {error}"
                    )
                event.set()

            def delete_album_handler(album):
                deletion_request = (
                    Photos.PHAssetCollectionChangeRequest.deleteAssetCollections_(
                        [album.collection]
                    )
                )

            self._phphotolibrary.performChanges_completionHandler_(
                lambda: delete_album_handler(album), completion_handler
            )

            event.wait()

    def folders(self):
        """ "Return list of folders in the library"""
        with objc.autorelease_pool():
            # these are single library mode only
            # this gets all user albums
            # albums = (
            #     Photos.PHAssetCollection.fetchAssetCollectionsWithType_subtype_options_(
            #         Photos.PHAssetCollectionTypeAlbum,
            #         Photos.PHAssetCollectionSubtypeAny,
            #         None,
            #     )
            # )
            #
            # this gets top level albums but also folders (PHCollectionList)
            folders = (
                Photos.PHCollectionList.fetchCollectionListsWithType_subtype_options_(
                    Photos.PHCollectionListTypeFolder,
                    Photos.PHCollectionListSubtypeAny,
                    None,
                )
            )
            for i in range(folders.count()):
                folder = folders.objectAtIndex_(i)
                print(folder)

    def asset(self, uuid: str) -> Asset:
        """Return Asset with uuid = uuid

        Args:
            uuid: str; UUID of image asset to fetch

        Returns:
            PhotoAsset object

        Raises:
            PhotoKitFetchFailed if fetch failed

        Note:
            uuid may be a UUID or the full local identifier of the requested asset
        """
        try:
            result = self._assets_from_uuid_list([uuid])
            return result[0]
        except Exception as e:
            raise PhotoKitFetchFailed(
                f"Fetch did not return result for uuid {uuid}: {e}"
            )

    def fetch_burst_uuid(self, burstid, all=False):
        """fetch PhotoAssets with burst ID = burstid

        Args:
            burstid: str, burst UUID
            all: return all burst assets; if False returns only those selected by the user (including the "key photo" even if user hasn't manually selected it)

        Returns:
            list of PhotoAsset objects

        Raises:
            PhotoKitFetchFailed if fetch failed
        """

        fetch_options = Photos.PHFetchOptions.alloc().init()
        fetch_options.setIncludeAllBurstAssets_(all)
        fetch_results = Photos.PHAsset.fetchAssetsWithBurstIdentifier_options_(
            burstid, fetch_options
        )
        if fetch_results and fetch_results.count() >= 1:
            return [
                self._asset_factory(fetch_results.objectAtIndex_(idx))
                for idx in range(fetch_results.count())
            ]
        else:
            raise PhotoKitFetchFailed(
                f"Fetch did not return result for burstid {burstid}"
            )

    def delete_assets(self, photoassets: list[PhotoAsset]):
        """Delete assets.

        Args:
            photoassets: list of PhotoAsset objects to delete
        Note that this will prompt the user to confirm deletion of assets.
        """
        with objc.autorelease_pool():
            assets = [asset.phasset for asset in photoassets]
            self._phphotolibrary.performChangesAndWait_error_(
                lambda: Photos.PHAssetChangeRequest.deleteAssets_(assets), None
            )

    # // Create an asset representation of the image file
    # [[PHPhotoLibrary sharedPhotoLibrary] performChanges:^{
    #     PHAssetCreationRequest *creationRequest = [PHAssetCreationRequest creationRequestForAsset];
    #     [creationRequest addResourceWithType:PHAssetResourceTypePhoto fileURL:imageURL options:nil];

    #     // Add the asset to the user's Photos library
    #     PHAssetCollectionChangeRequest *albumChangeRequest = [PHAssetCollectionChangeRequest changeRequestForAssetCollection:userLibrary];
    #     [albumChangeRequest addAssets:@[creationRequest.placeholderForCreatedAsset]];

    # } completionHandler:^(BOOL success, NSError *error) {
    #     if (!success) {
    #         NSLog(@"Failed to import image into Photos library: %@", error);
    #     } else {
    #         NSLog(@"Image imported successfully.");
    #     }
    # }];

    def add_photo(self, image_path: str | pathlib.Path | os.PathLike) -> Asset:
        """Add a photo to the Photos library

        Args:
            filepath: (str, pathlib.Path, os.PathLike) path to image file to add

        Returns:
            PhotoAsset object for added photo

        Raises:
            FileNotFoundError if image_path does not exist
            PhotoKitImportError if unable to import image
        """
        if not pathlib.Path(image_path).is_file():
            raise FileNotFoundError(f"Could not find image file {image_path}")

        image_path = str(image_path)
        with objc.autorelease_pool():
            image_url = NSURL.fileURLWithPath_(image_path)

            # user_library = self._default_album()
            # if not user_library:
            #     print("User's Photos library is not accessible.")
            #     return

            event = threading.Event()

            # Create an asset representation of the image file
            def completion_handler(success, error):
                if error:
                    raise PhotoKitImportError(f"Error importing asset: {error}")
                event.set()

            asset_uuid = None

            def import_image_changes_handler(image_url):
                nonlocal asset_uuid

                creation_request = (
                    Photos.PHAssetCreationRequest.creationRequestForAsset()
                )
                creation_request.addResourceWithType_fileURL_options_(
                    Photos.PHAssetResourceTypePhoto, image_url, None
                )

                asset_uuid = (
                    creation_request.placeholderForCreatedAsset().localIdentifier()
                )

                # # Add the asset to the user's Photos library
                # album_change_request = (
                #     Photos.PHAssetCollectionChangeRequest.changeRequestForAssetCollection_(
                #         user_library
                #     )
                # )
                # album_change_request.addAssets_(
                #     [creation_request.placeholderForCreatedAsset()]
                # )

            self._phphotolibrary.performChanges_completionHandler_(
                lambda: import_image_changes_handler(image_url), completion_handler
            )

            event.wait()

            return self.asset(asset_uuid)

    def _albums_from_uuid_list(self, uuids: list[str]) -> list[Album]:
        """Get albums from list of uuids

        Args:
            uuids: list of str (UUID of image assets to fetch)

        Returns: list of Album objects

        Raises:
            PhotoKitFetchFailed if fetch failed
        """

        uuids = [uuid.split("/")[0] for uuid in uuids]
        with objc.autorelease_pool():
            if PhotoLibrary.multi_library_mode():
                fetch_object = NSString.stringWithString_("Album")
                if fetch_result := self._phphotolibrary.fetchPHObjectsForUUIDs_entityName_(
                    uuids, fetch_object
                ):
                    return [
                        Album(self, fetch_result.objectAtIndex_(idx))
                        for idx in range(fetch_result.count())
                    ]
                else:
                    raise PhotoKitFetchFailed(
                        f"Fetch did not return result for uuid_list {uuids}"
                    )

            # single library mode
            albums = self.albums()
            return [album for album in albums if album.uuid in uuids]

    def _assets_from_uuid_list(self, uuids: list[str]) -> list[Asset]:
        """Get assets from list of uuids

        Args:
            uuids: list of str (UUID of image assets to fetch)

        Returns: list of Asset objects

        Raises:
            PhotoKitFetchFailed if fetch failed
        """

        # uuids may be full local identifiers (e.g. "1F2A3B4C-5D6E-7F8A-9B0C-D1E2F3A4B5C6/L0/001")
        # if so, strip off the "/L0/001" part
        uuids = [uuid.split("/")[0] for uuid in uuids]

        with objc.autorelease_pool():
            if PhotoLibrary.multi_library_mode():
                fetch_object = NSString.stringWithString_("Asset")
                if fetch_result := self._phphotolibrary.fetchPHObjectsForUUIDs_entityName_(
                    uuids, fetch_object
                ):
                    return [
                        self._asset_factory(fetch_result.objectAtIndex_(idx))
                        for idx in range(fetch_result.count())
                    ]
                else:
                    raise PhotoKitFetchFailed(
                        f"Fetch did not return result for uuid_list {uuids}"
                    )

            fetch_options = Photos.PHFetchOptions.alloc().init()
            fetch_result = Photos.PHAsset.fetchAssetsWithLocalIdentifiers_options_(
                uuids, fetch_options
            )
            if fetch_result and fetch_result.count() >= 1:
                return [
                    self._asset_factory(fetch_result.objectAtIndex_(idx))
                    for idx in range(fetch_result.count())
                ]
            else:
                raise PhotoKitFetchFailed(
                    f"Fetch did not return result for uuid_list {uuids}"
                )

    def _default_album(self):
        """Fetch the default Photos album"""
        if PhotoLibrary.multi_library_mode():
            raise NotImplementedError(
                "Fetching default album not implemented in multi-library mode"
            )

        # single library mode
        smart_albums = (
            Photos.PHAssetCollection.fetchAssetCollectionsWithType_subtype_options_(
                Photos.PHAssetCollectionTypeSmartAlbum,
                Photos.PHAssetCollectionSubtypeSmartAlbumUserLibrary,
                None,
            )
        )
        default_album = smart_albums.firstObject()
        return default_album

    def _asset_factory(self, phasset: Photos.PHAsset) -> Asset:
        """creates a PhotoAsset, VideoAsset, or LivePhotoAsset

        Args:
            phasset: PHAsset object

        Returns:
            PhotoAsset, VideoAsset, or LivePhotoAsset depending on type of PHAsset
        """

        if not isinstance(phasset, Photos.PHAsset):
            raise TypeError("phasset must be type PHAsset")

        media_type = phasset.mediaType()
        media_subtypes = phasset.mediaSubtypes()

        if media_subtypes & Photos.PHAssetMediaSubtypePhotoLive:
            return LivePhotoAsset(self._phimagemanager, phasset)
        elif media_type == Photos.PHAssetMediaTypeImage:
            return PhotoAsset(self._phimagemanager, phasset)
        elif media_type == Photos.PHAssetMediaTypeVideo:
            return VideoAsset(self._phimagemanager, phasset)
        else:
            raise PhotoKitMediaTypeError(f"Unknown media type: {media_type}")

    def __len__(self):
        """Return number of assets in library"""
        return len(self.assets())
