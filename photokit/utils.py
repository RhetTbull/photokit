""" Utility functions used in photokit """

from __future__ import annotations

import fnmatch
import os
import pathlib
import re
from typing import List, Optional, Union

from .unicode import normalize_fs_path


def list_directory(
    directory: Union[str, pathlib.Path],
    startswith: Optional[str] = None,
    endswith: Optional[str] = None,
    contains: Optional[str] = None,
    glob: Optional[str] = None,
    include_path: bool = False,
    case_sensitive: bool = False,
) -> List[Union[str, pathlib.Path]]:
    """List directory contents and return list of files or directories matching search criteria.
    Accounts for case-insensitive filesystems, unicode filenames. directory can be a str or a pathlib.Path object.

    Args:
        directory: directory to search
        startswith: string to match at start of filename
        endswith: string to match at end of filename
        contains: string to match anywhere in filename
        glob: shell-style glob pattern to match filename
        include_path: if True, return full path to file
        case_sensitive: if True, match case-sensitively

    Returns: List of files or directories matching search criteria as either str or pathlib.Path objects depending on the input type;
    returns empty list if directory is invalid or doesn't exist.

    """
    is_pathlib = isinstance(directory, pathlib.Path)
    if is_pathlib:
        directory = str(directory)

    if not os.path.isdir(directory):
        return []

    startswith = normalize_fs_path(startswith) if startswith else None
    endswith = normalize_fs_path(endswith) if endswith else None
    contains = normalize_fs_path(contains) if contains else None
    glob = normalize_fs_path(glob) if glob else None

    files = [normalize_fs_path(f) for f in os.listdir(directory)]
    if not case_sensitive:
        files_normalized = {f.lower(): f for f in files}
        files = [f.lower() for f in files]
        startswith = startswith.lower() if startswith else None
        endswith = endswith.lower() if endswith else None
        contains = contains.lower() if contains else None
        glob = glob.lower() if glob else None
    else:
        files_normalized = {f: f for f in files}

    if startswith:
        files = [f for f in files if f.startswith(startswith)]
    if endswith:
        endswith = normalize_fs_path(endswith)
        files = [f for f in files if f.endswith(endswith)]
    if contains:
        contains = normalize_fs_path(contains)
        files = [f for f in files if contains in f]
    if glob:
        glob = normalize_fs_path(glob)
        flags = re.IGNORECASE if not case_sensitive else 0
        rule = re.compile(fnmatch.translate(glob), flags)
        files = [f for f in files if rule.match(f)]

    files = [files_normalized[f] for f in files]

    if include_path:
        files = [os.path.join(directory, f) for f in files]
    if is_pathlib:
        files = [pathlib.Path(f) for f in files]

    return files


def increment_filename_with_count(
    filepath: str | pathlib.Path | os.PathLike,
    count: int = 0,
) -> tuple[str, int]:
    """Return filename (1).ext, etc if filename.ext exists

        If file exists in filename's parent folder with same stem as filename,
        add (1), (2), etc. until a non-existing filename is found.

    Args:
        filepath: str or pathlib.Path; full path, including file name
        count: int; starting increment value

    Returns:
        tuple of new filepath (or same if not incremented), count

    Note: This obviously is subject to race condition so using with caution.
    """
    dest = filepath if isinstance(filepath, pathlib.Path) else pathlib.Path(filepath)
    dest_files = list_directory(dest.parent, startswith=dest.stem)
    dest_files = [f.stem.lower() for f in dest_files]
    dest_new = f"{dest.stem} ({count})" if count else dest.stem
    dest_new = normalize_fs_path(dest_new)

    while dest_new.lower() in dest_files:
        count += 1
        dest_new = normalize_fs_path(f"{dest.stem} ({count})")
    dest = dest.parent / f"{dest_new}{dest.suffix}"
    return normalize_fs_path(str(dest)), count


def increment_filename(filepath: str | pathlib.Path | os.PathLike) -> str:
    """Return filename (1).ext, etc if filename.ext exists

        If file exists in filename's parent folder with same stem as filename,
        add (1), (2), etc. until a non-existing filename is found.

    Args:
        filepath: str or pathlib.Path; full path, including file name
        force: force the file count to increment by at least 1 even if filepath doesn't exist

    Returns:
        new filepath (or same if not incremented)

    Note: This obviously is subject to race condition so using with caution.
    """
    new_filepath, _ = increment_filename_with_count(filepath)
    return new_filepath
