"""Utilities for working with Objective-C objects"""

import datetime
import os
import pathlib

import Foundation


def NSURL_to_path(url: Foundation.NSURL) -> str:
    """Convert URL string as represented by NSURL to a path string"""
    nsurl = Foundation.NSURL.alloc().initWithString_(
        Foundation.NSString.alloc().initWithString_(str(url))
    )
    path = nsurl.fileSystemRepresentation().decode("utf-8")
    nsurl.dealloc()
    return path


def path_to_NSURL(path: str | pathlib.Path | os.PathLike) -> Foundation.NSURL:
    """Convert path string to NSURL"""
    pathstr = Foundation.NSString.alloc().initWithString_(str(path))
    url = Foundation.NSURL.fileURLWithPath_(pathstr)
    pathstr.dealloc()
    return url


def NSDate_to_datetime(nsdate: Foundation.NSDate) -> datetime.datetime:
    """Convert NSDate to datetime.datetime"""
    return datetime.datetime.fromtimestamp(nsdate.timeIntervalSince1970())
