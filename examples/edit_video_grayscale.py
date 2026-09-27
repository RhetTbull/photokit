"""
Example script to convert a video to grayscale using the PhotoKit edit API.

This demonstrates:
1. Loading a video asset from the Photos library
2. Applying a Core Image filter (grayscale) to each frame
3. Exporting the edited video
4. Saving the edit back to the Photos library

Usage: python edit_video_grayscale.py UUID
"""

import sys

import photokit
import AVFoundation
import Quartz
import Foundation
import Photos
import pathlib
import tempfile
import time

# Load the video from Photos library
pl = photokit.PhotoLibrary()
if len(sys.argv) != 2:
    sys.exit(f"Usage: {sys.argv[0]} UUID")
video = pl.asset(sys.argv[1])

print(f"Editing video: {video.original_filename}")
print(f"Duration: {video.duration:.2f} seconds")
print(f"Resolution: {video.pixel_width}x{video.pixel_height}")
print()

def convert_to_grayscale(original_path, adjustment_data):
    """
    Apply a grayscale filter to the video.

    Args:
        original_path: Path to the original video file
        adjustment_data: Existing adjustment data (if any)

    Returns:
        Tuple of (edited_video_path, new_adjustment_data) or None to cancel
    """
    print(f"Processing: {original_path}")

    # Load the video as an AVAsset
    video_url = Foundation.NSURL.fileURLWithPath_(original_path)
    av_asset = AVFoundation.AVAsset.assetWithURL_(video_url)

    # Define the filter to apply to each frame
    def apply_grayscale_filter(request):
        """Apply grayscale filter to a single frame"""
        source_image = request.sourceImage()

        # Create grayscale filter using CIColorMonochrome
        grayscale_filter = Quartz.CIFilter.filterWithName_("CIColorMonochrome")
        if grayscale_filter:
            grayscale_filter.setValue_forKey_(source_image, "inputImage")
            # Neutral gray color
            gray_color = Quartz.CIColor.colorWithRed_green_blue_(0.5, 0.5, 0.5)
            grayscale_filter.setValue_forKey_(gray_color, "inputColor")
            grayscale_filter.setValue_forKey_(1.0, "inputIntensity")

            output_image = grayscale_filter.valueForKey_("outputImage")
            if output_image:
                request.finishWithImage_context_(output_image, None)
                return

        # Fallback if filter fails
        request.finishWithImage_context_(source_image, None)

    # Create video composition with the filter
    composition = AVFoundation.AVMutableVideoComposition.videoCompositionWithAsset_applyingCIFiltersWithHandler_(
        av_asset,
        apply_grayscale_filter
    )

    # Set up export session
    temp_dir = tempfile.mkdtemp()
    output_path = pathlib.Path(temp_dir) / "grayscale.mov"
    output_url = Foundation.NSURL.fileURLWithPath_(str(output_path))

    export_session = AVFoundation.AVAssetExportSession.exportSessionWithAsset_presetName_(
        av_asset,
        AVFoundation.AVAssetExportPresetHighestQuality
    )

    if not export_session:
        print("ERROR: Failed to create export session")
        return None

    export_session.setOutputURL_(output_url)
    export_session.setOutputFileType_(AVFoundation.AVFileTypeQuickTimeMovie)
    export_session.setVideoComposition_(composition)

    # Start export
    print("Exporting video with grayscale filter...")
    completed = [False]
    last_progress = [0]

    def completion_handler():
        completed[0] = True

    export_session.exportAsynchronouslyWithCompletionHandler_(completion_handler)

    # Wait for export with progress updates
    start_time = time.time()
    timeout = 300.0  # 5 minutes

    while not completed[0] and (time.time() - start_time) < timeout:
        Foundation.NSRunLoop.currentRunLoop().runMode_beforeDate_(
            Foundation.NSDefaultRunLoopMode,
            Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.1)
        )

        # Show progress
        progress = int(export_session.progress() * 100)
        if progress > last_progress[0]:
            print(f"Progress: {progress}%")
            last_progress[0] = progress

    # Check export status
    if not completed[0]:
        print("ERROR: Export timeout")
        export_session.cancelExport()
        return None

    if export_session.status() != AVFoundation.AVAssetExportSessionStatusCompleted:
        error = export_session.error()
        print(f"ERROR: Export failed - {error}")
        return None

    print(f"✓ Export completed: {output_path}")

    # Create adjustment data to track this edit
    adjustment_data = Photos.PHAdjustmentData.alloc().initWithFormatIdentifier_formatVersion_data_(
        "com.example.photokit.video.grayscale",
        "1.0",
        Foundation.NSData.dataWithBytes_length_(b"grayscale", 9)
    )

    return (str(output_path), adjustment_data)


# Apply the edit
print("Starting video edit...")
print()
video.edit(convert_to_grayscale)
print()
print("✓ Video edit saved to Photos library!")
