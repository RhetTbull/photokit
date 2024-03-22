"""Watch for changes in Photo Library and export the changes to /private/tmp/photokit"""

import datetime
import os
import time

from PyObjCTools import AppHelper

import photokit

EXPORT_DIR = "/private/tmp/photokit"
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)

# maintain dict of processed images to avoid duplicates
# as sometimes the change observer gets called multiple times
# for the same image
_global_processed_images = {}


def change_observer(asset: photokit.AssetChanges):
    """Callback for observing changes to the Photo library"""
    print(f"change_observer: {datetime.datetime.now()}")
    for a in asset.added:
        print(f"added: {a.uuid} {a.original_filename}")
        if a.screenshot and a.uuid not in _global_processed_images:
            print(f"  Exporting new screenshot to {EXPORT_DIR}")
            results = a.export(EXPORT_DIR)
            print(f"  Exported: {results}")
            _global_processed_images[a.uuid] = results
    for a in asset.removed:
        print(f"removed: {a.uuid} {a.original_filename}")
    for a in asset.updated:
        print(f"updated: {a.uuid} {a.original_filename}")


def main():
    photolib = photokit.PhotoLibrary()
    print("Watching Photos library for changes")
    # observe_changes returns immediately, so we need to run the event loop
    # to keep the program running
    # The change_observer function will be called when changes are detected
    photolib.observe_changes(change_observer)
    AppHelper.runConsoleEventLoop(installInterrupt=True)


if __name__ == "__main__":
    main()
