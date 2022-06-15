# -*- coding: utf-8 -*-
"""
Ignore the unused imports, this file's purpose is to make visible
anything which a user might need to import from newspaper.
View newspaper/__init__.py for its usage.
"""

import feedparser

from .article import AsyncArticle
from .configuration import Configuration
from .settings import POPULAR_URLS
from .source import Source, AsyncSource
from .utils.helpers import extend_config, print_available_languages
from .utils.executor import Executor

from newspaper.api import (
    build,
    build_article,
    fulltext,
    hot
)

async def async_build(url: str = '', dry: bool = False, config = None, **kwargs) -> AsyncSource:
    """Returns a constructed source object without
    downloading or parsing the articles
    """
    config = config or Configuration()
    config = extend_config(config, kwargs)
    url = url or ''
    s = AsyncSource(url, config=config)
    if not dry:
        await s.async_build()
    return s


async def async_build_article(url: str = '', config=None, **kwargs) -> AsyncArticle:
    """Returns a constructed article object without downloading
    or parsing
    """
    config = config or Configuration()
    config = extend_config(config, kwargs)
    url = url or ''
    a = AsyncArticle(url, config=config)
    return a


def languages():
    """Returns a list of the supported languages
    """
    print_available_languages()


def popular_urls():
    """Returns a list of pre-extracted popular source urls
    """
    with open(POPULAR_URLS) as f:
        urls = ['http://' + u.strip() for u in f.readlines()]
        return urls


async def async_hot():
    """Returns a list of hit terms via google trends
    """
    return await Executor.run_as_async(hot)