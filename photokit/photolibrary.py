"""PhotoLibrary class for photokit"""

from __future__ import annotations

import pathlib

import objc
import Photos
from Foundation import NSURL, NSArray, NSNotificationCenter, NSObject, NSString

from .asset import LivePhotoAsset, PhotoAsset, VideoAsset
from .constants import (
    ACCESS_LEVEL_ADD_ONLY,
    ACCESS_LEVEL_READ_WRITE,
    MIN_SLEEP,
    PHOTOKIT_NOTIFICATION_FINISHED_REQUEST,
    PHOTOS_VERSION_CURRENT,
    PHOTOS_VERSION_ORIGINAL,
    PHOTOS_VERSION_UNADJUSTED,
    PHAccessLevelAddOnly,
    PHAccessLevelReadWrite,
    PHImageRequestOptionsVersionCurrent,
    PHImageRequestOptionsVersionOriginal,
    PHImageRequestOptionsVersionUnadjusted,
)
from .exceptions import (
    PhotoKitAuthError,
    PhotoKitCreateLibraryError,
    PhotoKitError,
    PhotoKitExportError,
    PhotoKitFetchFailed,
    PhotoKitImportError,
    PhotoKitMediaTypeError,
)
from .platform import get_macos_version
from .utils import NSURL_to_path


class PhotoLibrary:
    """Interface to PhotoKit PHImageManager and PHPhotoLibrary"""

    def __init__(self, library_path: str | None = None):
        """Initialize ImageManager instance.  Requests authorization to use the
        Photos library if authorization has not already been granted.

        Args:
            library_path: str, path to Photos library to use; if None, uses default shared library

        Raises:
            PhotoKitAuthError if unable to authorize access to PhotoKit

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
        if not library_path:
            self.single_library_mode = True
            self._phimagemanager = Photos.PHCachingImageManager.defaultManager()
            self._phphotolibrary = Photos.PHPhotoLibrary.sharedPhotoLibrary()
        else:
            # undocumented private API to get PHPhotoLibrary for a specific library
            self.single_library_mode = False
            Photos.PHPhotoLibrary.enableMultiLibraryMode()
            self._phphotolibrary = (
                Photos.PHPhotoLibrary.alloc().initWithPhotoLibraryURL_type_(
                    NSURL.fileURLWithPath_(library_path), 0
                )
            )
            self._phimagemanager = Photos.PHImageManager.alloc().init()

    @staticmethod
    def system_photo_library_path():
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
    def request_authorization(access_level: int = PHAccessLevelReadWrite):
        """Request authorization to user's Photos Library

        Returns: True if authorization granted, False otherwise

        Note: In actual practice, the terminal process running the python code
            will do the actual request. This method exists for use in bundled apps
            created with py2app, etc.
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

    def create_library(library_path: str) -> PhotoLibrary:
        """Create a new Photos library at library_path"""
        Photos.PHPhotoLibrary.enableMultiLibraryMode()
        photo_library = Photos.PHPhotoLibrary.alloc().initWithPhotoLibraryURL_type_(
            NSURL.fileURLWithPath_(library_path), 0
        )
        if photo_library.createPhotoLibraryUsingOptions_error_(None, None):
            return PhotoLibrary(library_path)
        else:
            raise PhotoKitCreateLibraryError(
                f"Unable to create library at {library_path}"
            )

    def albums(self):
        """Return list of albums in the library"""
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
            albums = Photos.PHCollectionList.fetchTopLevelUserCollectionsWithOptions_(
                None
            )
            for i in range(albums.count()):
                album = albums.objectAtIndex_(i)
                print(album)

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

    def fetch_uuid_list(self, uuid_list):
        """fetch PHAssets with uuids in uuid_list

        Args:
            uuid_list: list of str (UUID of image assets to fetch)

        Returns:
            list of PhotoAsset objects

        Raises:
            PhotoKitFetchFailed if fetch failed
        """

        with objc.autorelease_pool():
            if self.single_library_mode:
                fetch_options = Photos.PHFetchOptions.alloc().init()
                fetch_result = Photos.PHAsset.fetchAssetsWithLocalIdentifiers_options_(
                    uuid_list, fetch_options
                )
                if fetch_result and fetch_result.count() >= 1:
                    return [
                        self._asset_factory(fetch_result.objectAtIndex_(idx))
                        for idx in range(fetch_result.count())
                    ]
                else:
                    raise PhotoKitFetchFailed(
                        f"Fetch did not return result for uuid_list {uuid_list}"
                    )

            # multi-library mode
            fetch_object = NSString.stringWithString_("Asset")
            if fetch_result := self._phphotolibrary.fetchPHObjectsForUUIDs_entityName_(
                uuid_list, fetch_object
            ):
                return [
                    self._asset_factory(fetch_result.objectAtIndex_(idx))
                    for idx in range(fetch_result.count())
                ]
            else:
                raise PhotoKitFetchFailed(
                    f"Fetch did not return result for uuid_list {uuid_list}"
                )

    def fetch_uuid(self, uuid):
        """fetch PHAsset with uuid = uuid

        Args:
            uuid: str; UUID of image asset to fetch

        Returns:
            PhotoAsset object

        Raises:
            PhotoKitFetchFailed if fetch failed
        """
        try:
            result = self.fetch_uuid_list([uuid])
            return result[0]
        except:
            raise PhotoKitFetchFailed(f"Fetch did not return result for uuid {uuid}")

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

    def add_photo(self, filepath: str | pathlib.Path) -> PhotoAsset:
        """Add a photo to the Photos library

        Args:
            filepath: str or pathlib.Path, path to image file to add

        Returns:
            PhotoAsset object for added photo
        """
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

    def add_photo(self, image_path: str | pathlib.Path):
        if not pathlib.Path(image_path).is_file():
            raise FileNotFoundError(f"Could not find image file {image_path}")

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

            return asset_uuid

    def _default_album(self):
        # Fetch the default Photos album
        if self.single_library_mode:
            smart_albums = (
                Photos.PHAssetCollection.fetchAssetCollectionsWithType_subtype_options_(
                    Photos.PHAssetCollectionTypeSmartAlbum,
                    Photos.PHAssetCollectionSubtypeSmartAlbumUserLibrary,
                    None,
                )
            )
            default_album = smart_albums.firstObject()
            return default_album

    def _asset_factory(self, phasset):
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
