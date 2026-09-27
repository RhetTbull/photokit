"""Convert a photo in the Photos library to grayscale using the PhotoKit edit API.

Usage: python edit_photo_grayscale.py UUID

Edits are non-destructive; use Photos "Revert to Original" (or PhotoAsset.revert()) to undo.
"""

import sys

import photokit
import Quartz
import Foundation
import Photos
import pathlib
import tempfile

pl = photokit.PhotoLibrary()
if len(sys.argv) != 2:
    sys.exit(f"Usage: {sys.argv[0]} UUID")
photo = pl.asset(sys.argv[1])

def my_edit_callback(original_path, adjustment_data):
    print(f"Original path: {original_path}")
    print(f"Adjustment data: {adjustment_data}")

    # Create a CIImage from the file (Core Image is built on CoreGraphics)
    image_url = Foundation.NSURL.fileURLWithPath_(original_path)
    ci_image = Quartz.CIImage.imageWithContentsOfURL_(image_url)

    if not ci_image:
        print("Failed to load image")
        return None

    # Apply grayscale filter using CoreImage (built on CoreGraphics)
    # Create a color monochrome filter (black and white)
    grayscale_filter = Quartz.CIFilter.filterWithName_("CIColorMonochrome")
    grayscale_filter.setValue_forKey_(ci_image, "inputImage")

    # Set the color to grayscale (neutral gray)
    gray_color = Quartz.CIColor.colorWithRed_green_blue_(0.5, 0.5, 0.5)
    grayscale_filter.setValue_forKey_(gray_color, "inputColor")

    # Set the intensity (1.0 = full grayscale)
    grayscale_filter.setValue_forKey_(1.0, "inputIntensity")

    # Get the filtered output image
    output_image = grayscale_filter.valueForKey_("outputImage")

    # Create a CIContext for rendering
    ci_context = Quartz.CIContext.contextWithOptions_(None)

    # Render the CIImage to a CGImage (CoreGraphics)
    extent = output_image.extent()
    cg_image = ci_context.createCGImage_fromRect_(output_image, extent)

    if not cg_image:
        print("Failed to create CGImage from CIImage")
        return None

    # Create a temporary file for the edited image
    temp_dir = tempfile.mkdtemp()
    edited_path = pathlib.Path(temp_dir) / "edited.jpg"
    edited_url = Foundation.NSURL.fileURLWithPath_(str(edited_path))

    # Save using CGImageDestination (CoreGraphics API)
    image_dest = Quartz.CGImageDestinationCreateWithURL(
        edited_url,
        "public.jpeg",  # UTI for JPEG format
        1,  # one image
        None
    )

    if not image_dest:
        print("Failed to create image destination")
        return None

    # Set JPEG compression quality
    options = {
        Quartz.kCGImageDestinationLossyCompressionQuality: 0.95
    }

    # Add the CGImage to the destination
    Quartz.CGImageDestinationAddImage(image_dest, cg_image, options)

    # Finalize the file
    success = Quartz.CGImageDestinationFinalize(image_dest)

    if not success:
        print("Failed to save edited image")
        return None

    print(f"Edited image saved to: {edited_path}")

    # Create adjustment data to describe the edit
    adjustment_format_id = "com.example.photokit.grayscale"
    adjustment_version = "1.0"
    adjustment_data_content = b"grayscale_filter"

    new_adjustment_data = Photos.PHAdjustmentData.alloc().initWithFormatIdentifier_formatVersion_data_(
        adjustment_format_id,
        adjustment_version,
        Foundation.NSData.dataWithBytes_length_(adjustment_data_content, len(adjustment_data_content))
    )

    return (str(edited_path), new_adjustment_data)

photo.edit(my_edit_callback)
print("Edit completed successfully!")
