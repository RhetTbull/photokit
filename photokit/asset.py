"""Asset classes for photokit (represent PHAsset)"""

from __future__ import annotations

import copy
import datetime
import pathlib
import threading
import time
from typing import TYPE_CHECKING, Callable

import AVFoundation
import Foundation
import objc
import Photos
import Quartz
from Foundation import NSURL, NSArray, NSNotificationCenter, NSObject, NSString
from PyObjCTools import AppHelper
from wurlitzer import pipes

from .constants import (
    MIN_SLEEP,
    PHOTOKIT_NOTIFICATION_FINISHED_REQUEST,
    PHImageRequestOptionsVersionCurrent,
    PHImageRequestOptionsVersionOriginal,
    PHImageRequestOptionsVersionUnadjusted,
)
from .exceptions import (
    PhotoKitChangeError,
    PhotoKitExportError,
    PhotoKitFetchFailed,
    PhotoKitMediaTypeError,
)
from .fileutil import FileUtil
from .objc_utils import (
    NSDate_to_datetime,
    NSURL_to_path,
    datetime_to_NSDate,
    path_to_NSURL,
)
from .uti import get_preferred_uti_extension
from .utils import increment_filename

if TYPE_CHECKING:
    from .photolibrary import PhotoLibrary

# NOTES:
# - There are several techniques used for handling PhotoKit's various
#   asynchronous calls used in this code: event loop+notification, threading
#   event, while loop. I've experimented with each to find the one that works.
#   Happy to accept PRs from someone who knows PyObjC better than me and can
#   find a cleaner way to do this!

# BUG: LivePhotoAsset.export always exports edited version if Live Photo has been edited, even if other version requested
# add original=False to export instead of version= (and maybe others like path())
# make burst/live methods get uuid from self instead of passing as arg

# NOTE: This requires user have granted access to the terminal (e.g. Terminal.app or iTerm)
# to access Photos.  This should happen automatically the first time it's called. I've
# not figured out how to get the call to requestAuthorization_ to actually work in the case
# where Terminal doesn't automatically ask (e.g. if you use tcctutil to reset terminal priveleges)
# In the case where permission to use Photos was removed or reset, it looks like you also need
# to remove permission to for Full Disk Access then re-run the script in order for Photos to
# re-ask for permission

# TODO: implement this on photoasset:
# fetchAssetCollectionsContainingAsset:withType:options:
# TODO: Add reverseLocationData
# TODO: Move exporter code to separate class/file?
# TODO: add - (void)setTimeZone:(id)arg1 withDate:(id)arg2; for timewarp


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


class _PhotoKitNotificationDelegate(NSObject):
    """Handles notifications from NotificationCenter;
    used with asynchronous PhotoKit requests to stop event loop when complete
    """

    def liveNotification_(self, note):
        if note.name() == PHOTOKIT_NOTIFICATION_FINISHED_REQUEST:
            AppHelper.stopEventLoop()

    def __del__(self):
        pass
        # super(NSObject, self).dealloc()


class Asset:
    """Base class for PhotoKit PHAsset representation"""


class PhotoAsset(Asset):
    """PhotoKit PHAsset representation"""

    def __init__(self, library: PhotoLibrary, phasset: Photos.PHAsset):
        """Return a PhotoAsset object

        Args:
            library: a PhotoLibrary object
            phasset: a PHAsset object
        """
        self._library = library
        self._manager = self._library._phimagemanager
        self._phasset = phasset

    @property
    def phasset(self):
        """Return PHAsset instance"""
        return self._phasset

    @property
    def uuid(self):
        """Return UUID of PHAsset. This is the same as the local identifier minus the added path component."""
        return self._phasset.localIdentifier().split("/")[0]

    @property
    def local_identifier(self):
        """Return local identifier of PHAsset"""
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
    def date(self) -> datetime.datetime:
        """date asset was created as a naive datetime.datetime"""
        return NSDate_to_datetime(self.phasset.creationDate())

    @date.setter
    def date(self, date: datetime.datetime):
        """Set date asset was created"""

        def change_request_handler(change_request: Photos.PHAssetChangeRequest):
            creation_date = datetime_to_NSDate(date)
            change_request.setCreationDate_(creation_date)

        self._perform_changes(change_request_handler)

    @property
    def date_modified(self) -> datetime.datetime:
        """date asset was modified as a naive datetime.datetime"""
        return NSDate_to_datetime(self.phasset.modificationDate())

    @date_modified.setter
    def date_modified(self, date: datetime.datetime):
        """Set date asset was modified"""

        def change_request_handler(change_request: Photos.PHAssetChangeRequest):
            modification_date = datetime_to_NSDate(date)
            change_request.setModificationDate_(modification_date)

        self._perform_changes(change_request_handler)

    @property
    def date_added(self) -> datetime.datetime:
        """date asset was added to the library as a naive datetime.datetime"""
        # as best as I can tell there is no property to retrieve the date added
        # so get it from the database
        return self._library._photosdb.get_date_added_for_uuid(self.uuid)

    @date_added.setter
    def date_added(self, date: datetime.datetime):
        """Set date asset was added to the library"""

        def change_request_handler(change_request: Photos.PHAssetChangeRequest):
            added_date = datetime_to_NSDate(date)
            change_request.setAddedDate_(added_date)

        self._perform_changes(change_request_handler)

    @property
    def timezone_offset(self) -> int:
        """Timezone offset (seconds from GMT) of the asset"""
        # no property that I can find to retrieve this directly
        # so query the database instead
        return self._library._photosdb.get_timezone_for_uuid(self.uuid)[0]

    @timezone_offset.setter
    def timezone_offset(self, tz_offset: int):
        """Set timezone offset from UTC (in seconds) for asset"""

        def change_request_handler(change_request: Photos.PHAssetChangeRequest):
            timezone = Foundation.NSTimeZone.timeZoneForSecondsFromGMT_(tz_offset)
            date = change_request.creationDate()
            change_request.setTimeZone_withDate_(timezone, date)

        self._perform_changes(change_request_handler)

    @property
    def timezone(self) -> str:
        """The named timezone of the asset"""
        return self._library._photosdb.get_timezone_for_uuid(self.uuid)[2]

    @timezone.setter
    def timezone(self, tz: str):
        """Set the named timzone of the asset"""

        with objc.autorelease_pool():
            timezone = Foundation.NSTimeZone.timeZoneWithName_(tz)
            if not timezone:
                raise ValueError(f"Invalid timezone: {tz}")

            def change_request_handler(change_request: Photos.PHAssetChangeRequest):
                date = change_request.creationDate()
                change_request.setTimeZone_withDate_(timezone, date)

            self._perform_changes(change_request_handler)

    @property
    def location(self) -> tuple[float, float] | None:
        """location of the asset as a tuple of (latitude, longitude) or None if no location"""
        self._refresh()
        cllocation = self.phasset.location()
        return cllocation.coordinate() if cllocation else None

    @location.setter
    def location(self, latlon: tuple[float, float] | None):
        """Set location of asset to lat, lon or None"""

        with objc.autorelease_pool():

            def change_request_handler(change_request: Photos.PHAssetChangeRequest):
                if latlon is None:
                    location = Foundation.CLLocation.alloc().init()
                else:
                    location = (
                        Foundation.CLLocation.alloc().initWithLatitude_longitude_(
                            latlon[0], latlon[1]
                        )
                    )
                change_request.setLocation_(location)

            self._perform_changes(change_request_handler)

    @property
    def duration(self) -> float:
        """duration of the asset in seconds"""
        return self.phasset.duration()

    @property
    def favorite(self) -> bool:
        """True if asset is favorite, otherwise False"""
        self._refresh()
        return self.phasset.isFavorite()

    @favorite.setter
    def favorite(self, value: bool):
        """Set or clear favorite status of asset"""
        if self.favorite == value:
            return

        def change_request_handler(change_request: Photos.PHAssetChangeRequest):
            change_request.setFavorite_(value)

        self._perform_changes(change_request_handler)

    @property
    def hidden(self):
        """True if asset is hidden, otherwise False"""
        return self.phasset.isHidden()

    @property
    def keywords(self) -> list[str]:
        """Keywords associated with asset"""
        keywords = Photos.PHKeyword.fetchKeywordsForAsset_options_(self.phasset, None)
        return [keywords.objectAtIndex_(idx).title() for idx in range(keywords.count())]

    @keywords.setter
    def keywords(self, keywords: list[str]):
        """Set keywords associated with asset"""
        with objc.autorelease_pool():
            # get PHKeyword objects for current keywords
            current_phkeywords = self._library._keywords_from_title_list(self.keywords)

            # get PHKeyword objects for new keywords
            try:
                new_phkeywords = self._library._keywords_from_title_list(keywords)
            except PhotoKitFetchFailed:
                new_phkeywords = []
            phkeywords_titles = [kw.title() for kw in new_phkeywords]

            # are there any new keywords that need to be created?
            new_keywords = [kw for kw in keywords if kw not in phkeywords_titles]
            for kw in new_keywords:
                new_phkeywords.append(self._library.create_keyword(kw))

            phkeywords_to_remove = [
                kw for kw in current_phkeywords if kw not in new_phkeywords
            ]

            def change_request_handler(change_request: Photos.PHAssetChangeRequest):
                change_request.addKeywords_(new_phkeywords)
                if phkeywords_to_remove:
                    change_request.removeKeywords_(phkeywords_to_remove)

            self._perform_changes(change_request_handler)

    # Not working yet
    # @property
    # def persons(self) -> list[str]:
    #     """Persons in the asset"""
    #     persons = Photos.PHPerson.fetchPersonsInAsset_options_(self.phasset, None)
    #     person_list = []
    #     for idx in range(persons.count()):
    #         print(persons.objectAtIndex_(idx))
    #         person_list.append(persons.objectAtIndex_(idx).displayName())
    #     return person_list

    def metadata(self, version=PHImageRequestOptionsVersionCurrent):
        """Return dict of asset metadata

        Args:
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.metadata

    def uti(self, version=PHImageRequestOptionsVersionCurrent):
        """Return UTI of asset

        Args:
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
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

    def url(self, version=PHImageRequestOptionsVersionCurrent):
        """Return URL of asset

        Args:
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
        """
        imagedata = self._request_image_data(version=version)
        return str(imagedata.info["PHImageFileURLKey"])

    def path(self, version=PHImageRequestOptionsVersionCurrent):
        """Return path of asset

        Args:
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
        """
        imagedata = self._request_image_data(version=version)
        url = imagedata.info["PHImageFileURLKey"]
        return url.fileSystemRepresentation().decode("utf-8")

    def orientation(self, version=PHImageRequestOptionsVersionCurrent):
        """Return orientation of asset

        Args:
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.orientation

    @property
    def degraded(self, version=PHImageRequestOptionsVersionCurrent):
        """Return True if asset is degraded version

        Args:
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
        """
        imagedata = self._request_image_data(version=version)
        return imagedata.info["PHImageResultIsDegradedKey"]

    def _refresh(self):
        """Reload the asset from the library"""
        # this shouldn't be necessary but sometimes after creating a change (for example, toggling favorite)
        # the properties do not refresh
        self._phasset = self._library.asset(self.uuid)._phasset

    def _perform_changes(
        self, change_request_handler: Callable[[Photos.PHAssetChangeRequest], None]
    ):
        """Perform changes on a PHAsset

        Args:
            change_request_handler: a callable that will be passed the PHAssetChangeRequest to perform changes
        """

        with objc.autorelease_pool():
            event = threading.Event()

            def completion_handler(success, error):
                if error:
                    raise PhotoKitChangeError(f"Error changing asset: {error}")
                event.set()

            def _change_request_handler():
                change_request = Photos.PHAssetChangeRequest.changeRequestForAsset_(
                    self.phasset
                )
                change_request_handler(change_request)

            self._library._phphotolibrary.performChanges_completionHandler_(
                lambda: _change_request_handler(), completion_handler
            )

            event.wait()
            self._refresh()

    def export(
        self,
        dest,
        filename=None,
        version=PHImageRequestOptionsVersionCurrent,
        overwrite=False,
        raw=False,
        **kwargs,
    ):
        """Export image to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
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

    def _request_image_data(self, version=PHImageRequestOptionsVersionOriginal):
        """Request image data and metadata for self._phasset

        Args:
            version: which version to request
                     PHImageRequestOptionsVersionOriginal (default), request original highest fidelity version
                     PHImageRequestOptionsVersionCurrent, request current version with all edits
                     PHImageRequestOptionsVersionUnadjusted, request highest quality unadjusted version

        Returns:
            ImageData instance

        Raises:
            ValueError if passed invalid value for version
        """

        # reference: https://developer.apple.com/documentation/photokit/phimagemanager/3237282-requestimagedataandorientationfo?language=objc

        with objc.autorelease_pool():
            if version not in [
                PHImageRequestOptionsVersionCurrent,
                PHImageRequestOptionsVersionOriginal,
                PHImageRequestOptionsVersionUnadjusted,
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


class _SlowMoVideoExporter(NSObject):
    def initWithAVAsset_path_(self, avasset, path):
        """init helper class for exporting slow-mo video

        Args:
            avasset: AVAsset
            path: python str; path to export to
        """
        self = objc.super(_SlowMoVideoExporter, self).init()
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
        version=PHImageRequestOptionsVersionCurrent,
        overwrite=False,
        **kwargs,
    ):
        """Export video to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
            overwrite: bool, if True, overwrites destination file if it already exists; default is False
            **kwargs: used only to avoid issues with each asset type having slightly different export arguments

        Returns:
            List of path to exported image(s)

        Raises:
            ValueError if dest is not a valid directory
        """

        with objc.autorelease_pool():
            with pipes() as (out, err):
                if self.slow_mo and version == PHImageRequestOptionsVersionCurrent:
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
        self,
        dest,
        filename=None,
        version=PHImageRequestOptionsVersionCurrent,
        overwrite=False,
    ):
        """Export slow-motion video to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
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

            exporter = _SlowMoVideoExporter.alloc().initWithAVAsset_path_(
                videodata.asset, output_file
            )
            video = exporter.exportSlowMoVideo()
            # exporter.dealloc()
            return video

    # todo: rewrite this with NotificationCenter and App event loop?
    def _request_video_data(self, version=PHImageRequestOptionsVersionOriginal):
        """Request video data for self._phasset

        Args:
            version: which version to request
                     PHImageRequestOptionsVersionOriginal (default), request original highest fidelity version
                     PHImageRequestOptionsVersionCurrent, request current version with all edits
                     PHImageRequestOptionsVersionUnadjusted, request highest quality unadjusted version

        Raises:
            ValueError if passed invalid value for version
        """
        with objc.autorelease_pool():
            if version not in [
                PHImageRequestOptionsVersionCurrent,
                PHImageRequestOptionsVersionOriginal,
                PHImageRequestOptionsVersionUnadjusted,
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


class _LivePhotoRequest(NSObject):
    """Manage requests for live photo assets
    See: https://developer.apple.com/documentation/photokit/phimagemanager/1616984-requestlivephotoforasset?language=objc
    """

    def initWithManager_Asset_(self, manager, asset):
        self = objc.super(_LivePhotoRequest, self).init()
        if self is None:
            return None
        self.manager = manager
        self.asset = asset
        self.nc = NSNotificationCenter.defaultCenter()
        return self

    def requestLivePhotoResources(self, version=PHImageRequestOptionsVersionCurrent):
        """return the photos and video components of a live video as [PHAssetResource]"""

        with objc.autorelease_pool():
            options = Photos.PHLivePhotoRequestOptions.alloc().init()
            options.setNetworkAccessAllowed_(True)
            options.setVersion_(version)
            options.setDeliveryMode_(
                Photos.PHVideoRequestOptionsDeliveryModeHighQualityFormat
            )
            delegate = PhotoKitNotificationsDelegate.alloc().init()

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
        version=PHImageRequestOptionsVersionCurrent,
        overwrite=False,
        photo=True,
        video=True,
        **kwargs,
    ):
        """Export image to path

        Args:
            dest: str, path to destination directory
            filename: str, optional name of exported file; if not provided, defaults to asset's original filename
            version: which version of image (PHImageRequestOptionsVersionOriginal or PHImageRequestOptionsVersionCurrent)
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

                request = _LivePhotoRequest.alloc().initWithManager_Asset_(
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
