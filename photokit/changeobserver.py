"""Class to monitor Photo library for changes"""

import objc
import Photos


class ChangeObserver:
    """Monitor Photo library for changes"""

    def __init__(self):
        self.start()

    def start(self):
        """Start observing changes to the Photo library"""
        Photos.PHPhotoLibrary.sharedPhotoLibrary().registerChangeObserver_(self)

    def stop(self):
        """Stop observing changes to the Photo library"""
        Photos.PHPhotoLibrary.sharedPhotoLibrary().unregisterChangeObserver_(self)

    def photoLibraryDidChange_(self, change_instance):
        """Handle a change to the Photo library"""
        print("ChangeObserver.photoLibraryDidChange_()")
        print(change_instance)
