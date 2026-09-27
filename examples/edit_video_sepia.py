"""Apply a sepia tone filter to a video in the Photos library using the PhotoKit edit API.

Usage: python edit_video_sepia.py UUID
"""

import sys

import photokit
import AVFoundation
import Quartz
import Foundation
import Photos
import pathlib
import tempfile

pl = photokit.PhotoLibrary()
if len(sys.argv) != 2:
    sys.exit(f"Usage: {sys.argv[0]} UUID")
video = pl.asset(sys.argv[1])

print(f"Video: {video.original_filename}")
print(f"Duration: {video.duration} seconds")
print(f"Dimensions: {video.pixel_width}x{video.pixel_height}")

def apply_sepia_filter(original_path, adjustment_data):
    """Apply a sepia tone filter to the video"""
    print(f"Original video path: {original_path}")
    print(f"Adjustment data: {adjustment_data}")

    # Load the video asset
    video_url = Foundation.NSURL.fileURLWithPath_(original_path)
    av_asset = AVFoundation.AVAsset.assetWithURL_(video_url)

    print(f"Video duration: {av_asset.duration().value / av_asset.duration().timescale} seconds")

    # Create a video composition with Core Image filter
    composition = AVFoundation.AVMutableVideoComposition.videoCompositionWithAsset_applyingCIFiltersWithHandler_(
        av_asset,
        lambda request: apply_filter_to_frame(request)
    )

    # Create export session
    temp_dir = tempfile.mkdtemp()
    output_path = pathlib.Path(temp_dir) / "edited.mov"
    output_url = Foundation.NSURL.fileURLWithPath_(str(output_path))

    # Get compatible presets
    compatible_presets = AVFoundation.AVAssetExportSession.exportPresetsCompatibleWithAsset_(av_asset)
    print(f"Compatible presets: {compatible_presets}")

    # Use high quality preset
    preset = AVFoundation.AVAssetExportPresetHighestQuality
    if preset not in compatible_presets:
        print(f"Warning: {preset} not available, using first compatible preset")
        preset = compatible_presets[0] if len(compatible_presets) > 0 else None

    if not preset:
        print("No compatible export presets found!")
        return None

    export_session = AVFoundation.AVAssetExportSession.exportSessionWithAsset_presetName_(
        av_asset,
        preset
    )

    if not export_session:
        print("Failed to create export session")
        return None

    # Configure export session
    export_session.setOutputURL_(output_url)
    export_session.setOutputFileType_(AVFoundation.AVFileTypeQuickTimeMovie)
    export_session.setVideoComposition_(composition)

    print("Starting export...")

    # Export synchronously by running the runloop
    completed = [False]
    export_error = [None]

    def completion_handler():
        completed[0] = True
        if export_session.status() == AVFoundation.AVAssetExportSessionStatusFailed:
            export_error[0] = export_session.error()

    export_session.exportAsynchronouslyWithCompletionHandler_(completion_handler)

    # Wait for export to complete
    import time
    timeout = 300.0  # 5 minutes
    start_time = time.time()
    while not completed[0] and (time.time() - start_time) < timeout:
        Foundation.NSRunLoop.currentRunLoop().runMode_beforeDate_(
            Foundation.NSDefaultRunLoopMode,
            Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.1)
        )

        # Show progress
        progress = export_session.progress()
        if int(progress * 100) % 10 == 0:  # Print every 10%
            print(f"Export progress: {progress * 100:.0f}%")

    if not completed[0]:
        print("Export timeout!")
        export_session.cancelExport()
        return None

    if export_error[0]:
        print(f"Export failed: {export_error[0]}")
        return None

    if export_session.status() != AVFoundation.AVAssetExportSessionStatusCompleted:
        print(f"Export did not complete successfully. Status: {export_session.status()}")
        return None

    print(f"Export completed successfully to: {output_path}")

    # Create adjustment data
    adjustment_format_id = "com.example.photokit.sepia"
    adjustment_version = "1.0"
    adjustment_data_content = b"sepia_filter"

    new_adjustment_data = Photos.PHAdjustmentData.alloc().initWithFormatIdentifier_formatVersion_data_(
        adjustment_format_id,
        adjustment_version,
        Foundation.NSData.dataWithBytes_length_(adjustment_data_content, len(adjustment_data_content))
    )

    return (str(output_path), new_adjustment_data)


def apply_filter_to_frame(request):
    """Apply sepia filter to each frame"""
    # Get the source image
    source_image = request.sourceImage()

    # Create sepia filter (using color monochrome with a warm sepia color)
    sepia_filter = Quartz.CIFilter.filterWithName_("CISepiaTone")
    if not sepia_filter:
        request.finishWithImage_context_(source_image, None)
        return

    sepia_filter.setValue_forKey_(source_image, "inputImage")
    sepia_filter.setValue_forKey_(0.8, "inputIntensity")  # Sepia intensity

    # Get the filtered image
    output_image = sepia_filter.valueForKey_("outputImage")

    if output_image:
        request.finishWithImage_context_(output_image, None)
    else:
        request.finishWithImage_context_(source_image, None)


print("\nApplying sepia filter to video...")
video.edit(apply_sepia_filter)
print("Video edit completed successfully!")
