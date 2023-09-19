"""PHKeyword utilities"""

from __future__ import annotations

import Photos


def _fetch_keywords(titles: list[str]) -> list[Photos.PHKeyword]:
    """Fetch keywords with given local titles

    Args:
        titles: A list of titles (names) of the keywords

    Returns: A list of keywords with the given titles or an empty list if no keywords with the given titles

    Note: This only works in single library mode
    """
    if not titles:
        return []
    keywords = Photos.PHKeyword.fetchKeywordsWithTitles_options_(titles, None)
    keyword_list = []
    for idx in range(keywords.count()):
        keyword_list.append(keywords.objectAtIndex_(idx))
    return keyword_list
