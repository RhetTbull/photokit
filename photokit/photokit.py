""" Interface to Apple's PhotoKit framework for direct access to photos stored
    in the user's Photos library.  This is not by any means a complete implementation
    but does provide basic functionality for access metadata about media assets and
    exporting assets from the library.

"""

from __future__ import annotations

import copy
import pathlib
import sys
import threading
import time

from .platform import get_macos_version

# NOTES:
# - There are several techniques used for handling PhotoKit's various
#   asynchronous calls used in this code: event loop+notification, threading
#   event, while loop. I've experimented with each to find the one that works.
#   Happy to accept PRs from someone who knows PyObjC better than me and can
#   find a cleaner way to do this!

# TODO:
# BUG: LivePhotoAsset.export always exports edited version if Live Photo has been edited, even if other version requested
# add original=False to export instead of version= (and maybe others like path())
# make burst/live methods get uuid from self instead of passing as arg

# TODO: implement this on photoasset:
# fetchAssetCollectionsContainingAsset:withType:options:

assert sys.platform == "darwin"

import AVFoundation
import CoreServices
import Foundation
import objc
import Photos
import Quartz
from Foundation import NSURL, NSArray, NSNotificationCenter, NSObject, NSString
from PyObjCTools import AppHelper
from wurlitzer import pipes

from .fileutil import FileUtil
from .uti import get_preferred_uti_extension
from .utils import increment_filename

__all__ = [
    "NSURL_to_path",
    "path_to_NSURL",
    "PhotoLibrary.authorization_status",
    "request_photokit_authorization",
    "PhotoKitError",
    "PhotoKitFetchFailed",
    "PhotoKitAuthError",
    "PhotoKitExportError",
    "PhotoKitMediaTypeError",
    "ImageData",
    "AVAssetData",
    "PHAssetResourceData",
    "PhotoKitNotificationDelegate",
    "PhotoAsset",
    "SlowMoVideoExporter",
    "VideoAsset",
    "LivePhotoRequest",
    "LivePhotoAsset",
    "PhotoLibrary",
]

# NOTE: This requires user have granted access to the terminal (e.g. Terminal.app or iTerm)
# to access Photos.  This should happen automatically the first time it's called. I've
# not figured out how to get the call to requestAuthorization_ to actually work in the case
# where Terminal doesn't automatically ask (e.g. if you use tcctutil to reset terminal priveleges)
# In the case where permission to use Photos was removed or reset, it looks like you also need
# to remove permission to for Full Disk Access then re-run the script in order for Photos to
# re-ask for permission

### constants
# which version to export, use either PHOTOS_VERSION_X or the longer PhotoKit name
PHOTOS_VERSION_ORIGINAL = (
    PHImageRequestOptionsVersionOriginal
) = Photos.PHImageRequestOptionsVersionOriginal
PHOTOS_VERSION_UNADJUSTED = (
    PHImageRequestOptionsVersionUnadjusted
) = Photos.PHImageRequestOptionsVersionUnadjusted
PHOTOS_VERSION_CURRENT = (
    PHImageRequestOptionsVersionCurrent
) = Photos.PHImageRequestOptionsVersionCurrent

ACCESS_LEVEL_ADD_ONLY = PHAccessLevelAddOnly = Photos.PHAccessLevelAddOnly
ACCESS_LEVEL_READ_WRITE = PHAccessLevelReadWrite = Photos.PHAccessLevelReadWrite

# notification that gets sent to Notification Center
PHOTOKIT_NOTIFICATION_FINISHED_REQUEST = "PyPhotoKitNotificationFinishedRequest"

# minimum amount to sleep while waiting for export
MIN_SLEEP = 0.015


### utility functions
def NSURL_to_path(url):
    """Convert URL string as represented by NSURL to a path string"""
    nsurl = Foundation.NSURL.alloc().initWithString_(
        Foundation.NSString.alloc().initWithString_(str(url))
    )
    path = nsurl.fileSystemRepresentation().decode("utf-8")
    nsurl.dealloc()
    return path


def path_to_NSURL(path):
    """Convert path string to NSURL"""
    pathstr = Foundation.NSString.alloc().initWithString_(str(path))
    url = Foundation.NSURL.fileURLWithPath_(pathstr)
    pathstr.dealloc()
    return url


### exceptions
class PhotoKitError(Exception):
    """Base class for exceptions in this module."""

    pass


class PhotoKitFetchFailed(PhotoKitError):
    """Exception raised for errors in the input."""

    pass


class PhotoKitAuthError(PhotoKitError):
    """Exception raised if unable to authorize use of PhotoKit."""

    pass


class PhotoKitExportError(PhotoKitError):
    """Exception raised if unable to export asset."""

    pass


class PhotoKitImportError(PhotoKitError):
    """Exception raised if unable to import asset."""

    pass


class PhotoKitMediaTypeError(PhotoKitError):
    """Exception raised if an unknown mediaType() is encountered"""

    pass


class PhotoKitCreateLibraryError(PhotoKitError):
    """Exception raised if unable to create a PhotoLibrary object"""

    pass


### helper classes
class ImageData:
    """Simple class to hold the data passed to the handler for
    requestImageDataAndOrientationForAsset_options_resultHandler_
    """

    def __init__(
        self, metadata=None, uti=None, image_data=None, info=None, orientation=None
    ):
        self.metadata = metadata
        self.uti = uti
        self.image_data = image_data
        self.info = info
        self.orientation = orientation


class AVAssetData:
    """Simple class to hold the data passed to the handler for"""

    def __init__(self):
        self.asset = None
        self.export_session = None
        self.info = None
        self.audiomix = None


class PHAssetResourceData:
    """Simple class to hold data from
    requestDataForAssetResource:options:dataReceivedHandler:completionHandler:
    """

    def __init__(self):
        self.data = b""


class PhotoKitNotificationDelegate(NSObject):
    """Handles notifications from NotificationCenter;
    used with asynchronous PhotoKit requests to stop event loop when complete
    """

    def liveNotification_(self, note):
        if note.name() == PHOTOKIT_NOTIFICATION_FINISHED_REQUEST:
            AppHelper.stopEventLoop()

    def __del__(self):
        pass
        # super(NSObject, self).dealloc()


### main class implementation
class PhotoAsset:
    """PhotoKit PHAsset representation"""

    def __init__(self, manager, phasset):
        """Return a PhotoAsset object

        Args:
            manager = ImageManager object
            phasset: a PHAsset object
            uuid: UUID of the asset
        """
        self._manager = manager
        self._phasset = phasset

    @property
    def phasset(self):
        """Return PHAsset instance"""
        return self._phasset

    @property
    def uuid(self):
        """Return local identifier (UUID) of PHAsset"""
        return self._phasset.localIdentifier()

    @property
    def isphoto(self):
        """Return True if asset is photo (image), otherwise False"""
        return self.media_type == Photos.PHAssetMediaTypeImage

    @property
    def ismovie(self):
        """Return True if asset is movie (video), otherwise False"""
        return self.media_type == Photos.PHAssetMediaTypeVideo

    @property
    def isaudio(self):
        """Return True if asset is audio, otherwise False"""
        return self.media_type == Photos.PHAssetMediaTypeAudio

    @property
    def original_filename(self):
        """Return original filename asset was imported with"""
        resources = self._resources()
        for resource in resources:
            if (
                self.isphoto
                and resource.type() == Photos.PHAssetResourceTypePhoto
                or not self.isphoto
                and resource.type() == Photos.PHAssetResourceTypeVideo
            ):
                return resource.originalFilename()
        return None

    @property
    def raw_filename(self):
        """Return RAW filename for RAW+JPEG photos or None if no RAW asset"""
        resources = self._resources()
        for resource in resources:
            if (
                self.isphoto
                and resource.type() == Photos.PHAssetResourceTypeAlternatePhoto
            ):
                return resource.originalFilename()
        return None

    @property
    def hasadjustments(self):
        """Check to see if a PHAsset has adjustment data associated with it
        Returns False if no adjustments, True if any adjustments"""

        # reference: https://developer.apple.com/documentation/photokit/phassetresource/1623988-assetresourcesforasset?language=objc

        adjustment_resources = Photos.PHAssetResource.assetResourcesForAsset_(
            self.phasset
        )
        return any(
            (
                adjustment_resources.objectAtIndex_(idx).type()
                == Photos.PHAssetResourceTypeAdjustmentData
            )
            for idx in range(adjustment_resources.count())
        )

    @property
    def media_type(self):
        """media type such as image or video"""
        return self.phasset.mediaType()

    @property
    def media_subtypes(self):
        """media subtype"""
        return self.phasset.mediaSubtypes()

    @property
    def panorama(self):
        """return True if asset is panorama, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypePhotoPanorama)

    @property
    def hdr(self):
        """return True if asset is HDR, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypePhotoHDR)

    @property
    def screenshot(self):
        """return True if asset is screenshot, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypePhotoScreenshot)

    @property
    def live(self):
        """return True if asset is live, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypePhotoLive)

    @property
    def streamed(self):
        """return True if asset is streamed video, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypeVideoStreamed)

    @property
    def slow_mo(self):
        """return True if asset is slow motion (high frame rate) video, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypeVideoHighFrameRate)

    @property
    def time_lapse(self):
        """return True if asset is time lapse video, otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypeVideoTimelapse)

    @property
    def portrait(self):
        """return True if asset is portrait (depth effect), otherwise False"""
        return bool(self.media_subtypes & Photos.PHAssetMediaSubtypePhotoDepthEffect)

    @property
    def burstid(self):
        """return burstIdentifier of image if image is burst photo otherwise None"""
        return self.phasset.burstIdentifier()

    @property
    def burst(self):
        """return True if image is burst otherwise False"""
        return bool(self.burstid)

    @property
    def source_type(self):
        """the means by which the asset entered the user's library"""
        return self.phasset.sourceType()

    @property
    def pixel_width(self):
        """width in pixels"""
        return self.phasset.pixelWidth()

    @property
    def pixel_height(self):
        """height in pixels"""
        return self.phasset.pixelHeight()

    @property
    def date(self):
        """date asset was created"""
        return self.phasset.creationDate()

    @property
    def date_modified(self):
        """date asset was modified"""
        return self.phasset.modificationDate()

    @property
    def location(self):
        """location of the asset"""
        return self.phasset.location()

    @property
    def duration(self):
        """duration of the asset"""
        return self.phasset.duration()

    @property
    def favorite(self):
        """True if asset is favorite, otherwise False"""
        return self.phasset.isFavorite()

    @property
    def hidden(self):
        """True if asset is hidden, otherwise False"""
        return self.phasset.isHidden()

    def metadata(self, version=PHOTOS_VERSION_CURRENT):
        """Return dict of asset metadata

        Args:
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.metadata

    def uti(self, version=PHOTOS_VERSION_CURRENT):
        """Return UTI of asset

        Args:
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.uti

    def uti_raw(self):
        """Return UTI of RAW component of RAW+JPEG pair"""
        resources = self._resources()
        for resource in resources:
            if (
                self.isphoto
                and resource.type() == Photos.PHAssetResourceTypeAlternatePhoto
            ):
                return resource.uniformTypeIdentifier()
        return None

    def url(self, version=PHOTOS_VERSION_CURRENT):
        """Return URL of asset

        Args:
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
        """
        imagedata = self._request_image_data(version=version)
        return str(imagedata.info["PHImageFileURLKey"])

    def path(self, version=PHOTOS_VERSION_CURRENT):
        """Return path of asset

        Args:
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
        """
        imagedata = self._request_image_data(version=version)
        url = imagedata.info["PHImageFileURLKey"]
        return url.fileSystemRepresentation().decode("utf-8")

    def orientation(self, version=PHOTOS_VERSION_CURRENT):
        """Return orientation of asset

        Args:
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.orientation

    @property
    def degraded(self, version=PHOTOS_VERSION_CURRENT):
        """Return True if asset is degraded version

        Args:
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.info["PHImageResultIsDegradedKey"]

    def export(
        self,
        dest,
        filename=None,
        version=PHOTOS_VERSION_CURRENT,
        overwrite=False,
        raw=False,
        **kwargs,
    ):
        """Export image to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
            overwrite: bool, if True, overwrites destination file if it already exists; default is False
            raw: bool, if True, export RAW component of RAW+JPEG pair, default is False
            **kwargs: used only to avoid issues with each asset type having slightly different export arguments

        Returns:
            List of path to exported image(s)

        Raises:
            ValueError if dest is not a valid directory
        """

        with objc.autorelease_pool():
            with pipes() as (out, err):
                filename = (
                    pathlib.Path(filename)
                    if filename
                    else pathlib.Path(self.original_filename)
                )

                dest = pathlib.Path(dest)
                if not dest.is_dir():
                    raise ValueError("dest must be a valid directory: {dest}")

                output_file = None
                if self.isphoto:
                    # will hold exported image data and needs to be cleaned up at end
                    imagedata = None
                    if raw:
                        # export the raw component
                        resources = self._resources()
                        for resource in resources:
                            if (
                                resource.type()
                                == Photos.PHAssetResourceTypeAlternatePhoto
                            ):
                                data = self._request_resource_data(resource)
                                suffix = pathlib.Path(self.raw_filename).suffix
                                ext = suffix[1:] if suffix else ""
                                break
                        else:
                            raise PhotoKitExportError(
                                "Could not get image data for RAW photo"
                            )
                    else:
                        # TODO: if user has selected use RAW as original, this returns the RAW
                        # can get the jpeg with resource.type() == Photos.PHAssetResourceTypePhoto
                        imagedata = self._request_image_data(version=version)
                        if not imagedata.image_data:
                            raise PhotoKitExportError("Could not get image data")
                        ext = get_preferred_uti_extension(imagedata.uti)
                        data = imagedata.image_data

                    output_file = dest / f"{filename.stem}.{ext}"

                    if not overwrite:
                        output_file = pathlib.Path(increment_filename(output_file))

                    with open(output_file, "wb") as fd:
                        fd.write(data)

                    if imagedata:
                        del imagedata
                elif self.ismovie:
                    videodata = self._request_video_data(version=version)
                    if videodata.asset is None:
                        raise PhotoKitExportError("Could not get video for asset")

                    url = videodata.asset.URL()
                    path = pathlib.Path(NSURL_to_path(url))
                    if not path.is_file():
                        raise FileNotFoundError("Could not get path to video file")
                    ext = path.suffix
                    output_file = dest / f"{filename.stem}{ext}"

                    if not overwrite:
                        output_file = pathlib.Path(increment_filename(output_file))

                    FileUtil.copy(path, output_file)

                return [str(output_file)]

    def _request_image_data(self, version=PHOTOS_VERSION_ORIGINAL):
        """Request image data and metadata for self._phasset

        Args:
            version: which version to request
                     PHOTOS_VERSION_ORIGINAL (default), request original highest fidelity version
                     PHOTOS_VERSION_CURRENT, request current version with all edits
                     PHOTOS_VERSION_UNADJUSTED, request highest quality unadjusted version

        Returns:
            ImageData instance

        Raises:
            ValueError if passed invalid value for version
        """

        # reference: https://developer.apple.com/documentation/photokit/phimagemanager/3237282-requestimagedataandorientationfo?language=objc

        with objc.autorelease_pool():
            if version not in [
                PHOTOS_VERSION_CURRENT,
                PHOTOS_VERSION_ORIGINAL,
                PHOTOS_VERSION_UNADJUSTED,
            ]:
                raise ValueError("Invalid value for version")

            options_request = Photos.PHImageRequestOptions.alloc().init()
            options_request.setNetworkAccessAllowed_(True)
            options_request.setSynchronous_(True)
            options_request.setVersion_(version)
            options_request.setDeliveryMode_(
                Photos.PHImageRequestOptionsDeliveryModeHighQualityFormat
            )
            requestdata = ImageData()
            event = threading.Event()

            def handler(imageData, dataUTI, orientation, info):
                """result handler for requestImageDataAndOrientationForAsset_options_resultHandler_
                all returned by the request is set as properties of nonlocal data (Fetchdata object)
                """

                nonlocal requestdata

                options = {Quartz.kCGImageSourceShouldCache: Foundation.kCFBooleanFalse}
                imgSrc = Quartz.CGImageSourceCreateWithData(imageData, options)
                requestdata.metadata = Quartz.CGImageSourceCopyPropertiesAtIndex(
                    imgSrc, 0, options
                )
                requestdata.uti = dataUTI
                requestdata.orientation = orientation
                requestdata.info = info
                requestdata.image_data = imageData

                event.set()

            self._manager.requestImageDataAndOrientationForAsset_options_resultHandler_(
                self.phasset, options_request, handler
            )
            event.wait()
            # options_request.dealloc()

            # not sure why this is needed -- some weird ref count thing maybe
            # if I don't do this, memory leaks
            data = copy.copy(requestdata)
            del requestdata
            return data

    def _request_resource_data(self, resource):
        """Request asset resource data (either photo or video component)

        Args:
            resource: PHAssetResource to request

        Raises:
        """

        with objc.autorelease_pool():
            resource_manager = Photos.PHAssetResourceManager.defaultManager()
            options = Photos.PHAssetResourceRequestOptions.alloc().init()
            options.setNetworkAccessAllowed_(True)

            requestdata = PHAssetResourceData()
            event = threading.Event()

            def handler(data):
                """result handler for requestImageDataAndOrientationForAsset_options_resultHandler_
                all returned by the request is set as properties of nonlocal data (Fetchdata object)
                """

                nonlocal requestdata

                requestdata.data += data

            def completion_handler(error):
                if error:
                    raise PhotoKitExportError(
                        "Error requesting data for asset resource"
                    )
                event.set()

            resource_manager.requestDataForAssetResource_options_dataReceivedHandler_completionHandler_(
                resource, options, handler, completion_handler
            )

            event.wait()

            # not sure why this is needed -- some weird ref count thing maybe
            # if I don't do this, memory leaks
            data = copy.copy(requestdata.data)
            del requestdata
            return data

    def _make_result_handle_(self, data):
        """Make handler function and threading event to use with
        requestImageDataAndOrientationForAsset_options_resultHandler_
        data: Fetchdata class to hold resulting metadata
        returns: handler function, threading.Event() instance
        Following call to requestImageDataAndOrientationForAsset_options_resultHandler_,
        data will hold data from the fetch"""

        event = threading.Event()

        def handler(imageData, dataUTI, orientation, info):
            """result handler for requestImageDataAndOrientationForAsset_options_resultHandler_
            all returned by the request is set as properties of nonlocal data (Fetchdata object)
            """

            nonlocal data

            options = {Quartz.kCGImageSourceShouldCache: Foundation.kCFBooleanFalse}
            imgSrc = Quartz.CGImageSourceCreateWithData(imageData, options)
            data.metadata = Quartz.CGImageSourceCopyPropertiesAtIndex(
                imgSrc, 0, options
            )
            data.uti = dataUTI
            data.orientation = orientation
            data.info = info
            data.image_data = imageData

            event.set()

        return handler, event

    def _resources(self):
        """Return list of PHAssetResource for object"""
        resources = Photos.PHAssetResource.assetResourcesForAsset_(self.phasset)
        return [resources.objectAtIndex_(idx) for idx in range(resources.count())]


class SlowMoVideoExporter(NSObject):
    def initWithAVAsset_path_(self, avasset, path):
        """init helper class for exporting slow-mo video

        Args:
            avasset: AVAsset
            path: python str; path to export to
        """
        self = objc.super(SlowMoVideoExporter, self).init()
        if self is None:
            return None
        self.avasset = avasset
        self.url = path_to_NSURL(path)
        self.nc = NSNotificationCenter.defaultCenter()
        return self

    def exportSlowMoVideo(self):
        """export slow-mo video with AVAssetExportSession

        Returns:
            path to exported file
        """

        with objc.autorelease_pool():
            exporter = (
                AVFoundation.AVAssetExportSession.alloc().initWithAsset_presetName_(
                    self.avasset, AVFoundation.AVAssetExportPresetHighestQuality
                )
            )
            exporter.setOutputURL_(self.url)
            exporter.setOutputFileType_(AVFoundation.AVFileTypeQuickTimeMovie)
            exporter.setShouldOptimizeForNetworkUse_(True)

            self.done = False

            def handler():
                """result handler for exportAsynchronouslyWithCompletionHandler"""
                self.done = True

            exporter.exportAsynchronouslyWithCompletionHandler_(handler)
            # wait for export to complete
            # would be more elegant to use a dispatch queue, notification, or thread event to wait
            # but I can't figure out how to make that work and this does work
            while True:
                status = exporter.status()
                if status == AVFoundation.AVAssetExportSessionStatusCompleted:
                    break
                elif status not in (
                    AVFoundation.AVAssetExportSessionStatusWaiting,
                    AVFoundation.AVAssetExportSessionStatusExporting,
                ):
                    raise PhotoKitExportError(
                        f"Error encountered during exportAsynchronouslyWithCompletionHandler: status = {status}"
                    )
                time.sleep(MIN_SLEEP)

            exported_path = NSURL_to_path(exporter.outputURL())
            # exporter.dealloc()
            return exported_path

    def __del__(self):
        self.avasset = None
        self.url.dealloc()
        self.url = None
        self.done = None
        self.nc = None


class VideoAsset(PhotoAsset):
    """PhotoKit PHAsset representation of video asset"""

    # TODO: doesn't work for slow-mo videos
    # see https://stackoverflow.com/questions/26152396/how-to-access-nsdata-nsurl-of-slow-motion-videos-using-photokit
    # https://developer.apple.com/documentation/photokit/phimagemanager/1616935-requestavassetforvideo?language=objc
    # https://developer.apple.com/documentation/photokit/phimagemanager/1616981-requestexportsessionforvideo?language=objc
    # above 10.15 only
    def export(
        self,
        dest,
        filename=None,
        version=PHOTOS_VERSION_CURRENT,
        overwrite=False,
        **kwargs,
    ):
        """Export video to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
            overwrite: bool, if True, overwrites destination file if it already exists; default is False
            **kwargs: used only to avoid issues with each asset type having slightly different export arguments

        Returns:
            List of path to exported image(s)

        Raises:
            ValueError if dest is not a valid directory
        """

        with objc.autorelease_pool():
            with pipes() as (out, err):
                if self.slow_mo and version == PHOTOS_VERSION_CURRENT:
                    return [
                        self._export_slow_mo(
                            dest,
                            filename=filename,
                            version=version,
                            overwrite=overwrite,
                        )
                    ]

                filename = (
                    pathlib.Path(filename)
                    if filename
                    else pathlib.Path(self.original_filename)
                )

                dest = pathlib.Path(dest)
                if not dest.is_dir():
                    raise ValueError("dest must be a valid directory: {dest}")

                output_file = None
                videodata = self._request_video_data(version=version)
                if videodata.asset is None:
                    raise PhotoKitExportError("Could not get video for asset")

                url = videodata.asset.URL()
                path = pathlib.Path(NSURL_to_path(url))
                del videodata
                if not path.is_file():
                    raise FileNotFoundError("Could not get path to video file")
                ext = path.suffix
                output_file = dest / f"{filename.stem}{ext}"

                if not overwrite:
                    output_file = pathlib.Path(increment_filename(output_file))

                FileUtil.copy(path, output_file)

                return [str(output_file)]

    def _export_slow_mo(
        self, dest, filename=None, version=PHOTOS_VERSION_CURRENT, overwrite=False
    ):
        """Export slow-motion video to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
            overwrite: bool, if True, overwrites destination file if it already exists; default is False

        Returns:
            Path to exported image

        Raises:
            ValueError if dest is not a valid directory
        """
        with objc.autorelease_pool():
            if not self.slow_mo:
                raise PhotoKitMediaTypeError("Not a slow-mo video")

            videodata = self._request_video_data(version=version)
            if (
                not isinstance(videodata.asset, AVFoundation.AVComposition)
                or len(videodata.asset.tracks()) != 2
            ):
                raise PhotoKitMediaTypeError("Does not appear to be slow-mo video")

            filename = (
                pathlib.Path(filename)
                if filename
                else pathlib.Path(self.original_filename)
            )

            dest = pathlib.Path(dest)
            if not dest.is_dir():
                raise ValueError("dest must be a valid directory: {dest}")

            output_file = dest / f"{filename.stem}.mov"

            if not overwrite:
                output_file = pathlib.Path(increment_filename(output_file))

            exporter = SlowMoVideoExporter.alloc().initWithAVAsset_path_(
                videodata.asset, output_file
            )
            video = exporter.exportSlowMoVideo()
            # exporter.dealloc()
            return video

    # todo: rewrite this with NotificationCenter and App event loop?
    def _request_video_data(self, version=PHOTOS_VERSION_ORIGINAL):
        """Request video data for self._phasset

        Args:
            version: which version to request
                     PHOTOS_VERSION_ORIGINAL (default), request original highest fidelity version
                     PHOTOS_VERSION_CURRENT, request current version with all edits
                     PHOTOS_VERSION_UNADJUSTED, request highest quality unadjusted version

        Raises:
            ValueError if passed invalid value for version
        """
        with objc.autorelease_pool():
            if version not in [
                PHOTOS_VERSION_CURRENT,
                PHOTOS_VERSION_ORIGINAL,
                PHOTOS_VERSION_UNADJUSTED,
            ]:
                raise ValueError("Invalid value for version")

            options_request = Photos.PHVideoRequestOptions.alloc().init()
            options_request.setNetworkAccessAllowed_(True)
            options_request.setVersion_(version)
            options_request.setDeliveryMode_(
                Photos.PHVideoRequestOptionsDeliveryModeHighQualityFormat
            )
            requestdata = AVAssetData()
            event = threading.Event()

            def handler(asset, audiomix, info):
                """result handler for requestAVAssetForVideo:asset options:options resultHandler"""
                nonlocal requestdata

                requestdata.asset = asset
                requestdata.audiomix = audiomix
                requestdata.info = info

                event.set()

            self._manager.requestAVAssetForVideo_options_resultHandler_(
                self.phasset, options_request, handler
            )
            event.wait()

            # not sure why this is needed -- some weird ref count thing maybe
            # if I don't do this, memory leaks
            data = copy.copy(requestdata)
            del requestdata
            return data


class LivePhotoRequest(NSObject):
    """Manage requests for live photo assets
    See: https://developer.apple.com/documentation/photokit/phimagemanager/1616984-requestlivephotoforasset?language=objc
    """

    def initWithManager_Asset_(self, manager, asset):
        self = objc.super(LivePhotoRequest, self).init()
        if self is None:
            return None
        self.manager = manager
        self.asset = asset
        self.nc = NSNotificationCenter.defaultCenter()
        return self

    def requestLivePhotoResources(self, version=PHOTOS_VERSION_CURRENT):
        """return the photos and video components of a live video as [PHAssetResource]"""

        with objc.autorelease_pool():
            options = Photos.PHLivePhotoRequestOptions.alloc().init()
            options.setNetworkAccessAllowed_(True)
            options.setVersion_(version)
            options.setDeliveryMode_(
                Photos.PHVideoRequestOptionsDeliveryModeHighQualityFormat
            )
            delegate = PhotoKitNotificationDelegate.alloc().init()

            self.nc.addObserver_selector_name_object_(
                delegate, "liveNotification:", None, None
            )

            self.live_photo = None

            def handler(result, info):
                """result handler for requestLivePhotoForAsset:targetSize:contentMode:options:resultHandler:"""
                if not info["PHImageResultIsDegradedKey"]:
                    self.live_photo = result
                    self.info = info
                    self.nc.postNotificationName_object_(
                        PHOTOKIT_NOTIFICATION_FINISHED_REQUEST, self
                    )

            try:
                self.manager.requestLivePhotoForAsset_targetSize_contentMode_options_resultHandler_(
                    self.asset,
                    Photos.PHImageManagerMaximumSize,
                    Photos.PHImageContentModeDefault,
                    options,
                    handler,
                )
                AppHelper.runConsoleEventLoop(installInterrupt=True)
            except KeyboardInterrupt:
                AppHelper.stopEventLoop()
            finally:
                pass

            asset_resources = Photos.PHAssetResource.assetResourcesForLivePhoto_(
                self.live_photo
            )

            # not sure why this is needed -- some weird ref count thing maybe
            # if I don't do this, memory leaks
            data = copy.copy(asset_resources)
            del asset_resources
            return data

    def __del__(self):
        self.manager = None
        self.asset = None
        self.nc = None
        self.live_photo = None
        self.info = None
        # super(NSObject, self).dealloc()


class LivePhotoAsset(PhotoAsset):
    """Represents a live photo"""

    def export(
        self,
        dest,
        filename=None,
        version=PHOTOS_VERSION_CURRENT,
        overwrite=False,
        photo=True,
        video=True,
        **kwargs,
    ):
        """Export image to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHOTOS_VERSION_ORIGINAL or PHOTOS_VERSION_CURRENT)
            overwrite: bool, if True, overwrites destination file if it already exists; default is False
            photo: bool, if True, export photo component of live photo
            video: bool, if True, export live video component of live photo
            **kwargs: used only to avoid issues with each asset type having slightly different export arguments

        Returns:
            list of [path to exported image and/or video]

        Raises:
            ValueError if dest is not a valid directory
            PhotoKitExportError if error during export
        """

        with objc.autorelease_pool():
            with pipes() as (out, err):
                filename = (
                    pathlib.Path(filename)
                    if filename
                    else pathlib.Path(self.original_filename)
                )

                dest = pathlib.Path(dest)
                if not dest.is_dir():
                    raise ValueError("dest must be a valid directory: {dest}")

                request = LivePhotoRequest.alloc().initWithManager_Asset_(
                    self._manager, self.phasset
                )
                resources = request.requestLivePhotoResources(version=version)

                video_resource = None
                photo_resource = None
                for resource in resources:
                    if resource.type() == Photos.PHAssetResourceTypePairedVideo:
                        video_resource = resource
                    elif resource.type() == Photos.PHAssetMediaTypeImage:
                        photo_resource = resource

                if not video_resource or not photo_resource:
                    raise PhotoKitExportError(
                        "Did not find photo/video resources for live photo"
                    )

                photo_ext = get_preferred_uti_extension(
                    photo_resource.uniformTypeIdentifier()
                )
                photo_output_file = dest / f"{filename.stem}.{photo_ext}"
                video_ext = get_preferred_uti_extension(
                    video_resource.uniformTypeIdentifier()
                )
                video_output_file = dest / f"{filename.stem}.{video_ext}"

                if not overwrite:
                    photo_output_file = pathlib.Path(
                        increment_filename(photo_output_file)
                    )
                    video_output_file = pathlib.Path(
                        increment_filename(video_output_file)
                    )

                exported = []
                if photo:
                    data = self._request_resource_data(photo_resource)
                    # image_data = self.request_image_data(version=version)
                    with open(photo_output_file, "wb") as fd:
                        fd.write(data)
                    exported.append(str(photo_output_file))
                    del data
                if video:
                    data = self._request_resource_data(video_resource)
                    with open(video_output_file, "wb") as fd:
                        fd.write(data)
                    exported.append(str(video_output_file))
                    del data

                request.dealloc()
                return exported


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
