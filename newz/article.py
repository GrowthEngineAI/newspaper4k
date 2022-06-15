
from urllib.parse import urlparse

import httpx
from fileio import File
from . import network
from . import nlp
from .configuration import Configuration
from .utils.executor import Executor
from .utils.helpers import (
    extract_meta_refresh
)
from .utils import logger as log
from newspaper.article import (
    ArticleDownloadState,
    ArticleException,
    Article
)


class AsyncArticle(Article):
    """Article objects abstract an online news article page
    """
    def __init__(self, url: str, title: str = '', source_url: str = '', num_keywords: int = 10, config = None, **kwargs):
        self.num_keywords = num_keywords
        config = config or Configuration()
        super().__init__(url = url, title = title, source_url = source_url, config = config, **kwargs)


    async def _async_parse_scheme_file(self, path):
        fpath = File(path)
        try:
            async with fpath.async_open('r') as fin:
                return await fin.read()
        except OSError as e:
            self.download_state = ArticleDownloadState.FAILED_RESPONSE
            self.download_exception_msg = e.strerror
            return None

    async def _async_parse_scheme_http(self):
        try:
            return await network.async_get_html_2XX_only(self.url, self.config)
        except httpx.RequestError as e:
            self.download_state = ArticleDownloadState.FAILED_RESPONSE
            self.download_exception_msg = str(e)
            return None

    async def async_build(self):
        """Build a lone article from a URL independent of the source (newspaper).
        Don't normally call this method b/c it's good to multithread articles
        on a source (newspaper) level.
        """
        await self.async_download()
        await self.async_parse()
        #self.parse()
        await self.async_nlp()
    


    async def async_download(self, input_html=None, title=None, recursion_counter=0):
        """Downloads the link's HTML content, don't use if you are batch async
        downloading articles

        recursion_counter (currently 1) stops refreshes that are potentially
        infinite
        """
        if input_html is None:
            parsed_url = urlparse(self.url)
            if parsed_url.scheme == "file":
                html = await self._async_parse_scheme_file(parsed_url.path)
            else:
                html = await self._async_parse_scheme_http()
            if html is None:
                log.debug(f'Download failed on URL {self.url} because of {self.download_exception_msg}')
                return
        else:
            html = input_html

        if self.config.follow_meta_refresh:
            meta_refresh_url = extract_meta_refresh(html)
            if meta_refresh_url and recursion_counter < 1:
                return await self.async_download(
                    input_html = await network.async_get_html(meta_refresh_url),
                    recursion_counter = recursion_counter + 1
                )
        self.set_html(html)
        self.set_title(title)
    
    async def async_parse(self):
        return await Executor.run_as_async(self.parse)

    async def async_nlp(self):
        """Keyword extraction wrapper
        """
        self.throw_if_not_downloaded_verbose()
        self.throw_if_not_parsed_verbose()

        lang = self.config.get_language()
        nlp.load_stopwords(lang)

        text_keyws = list(nlp.keywords(self.text, num_keywords = self.num_keywords, language = lang).keys())
        title_keyws = list(nlp.keywords(self.title, num_keywords = self.num_keywords, language = lang).keys())
        keyws = list(set(title_keyws + text_keyws))
        self.set_keywords(keyws)

        max_sents = self.config.MAX_SUMMARY_SENT
        summary_sents = await nlp.async_summarize(title=self.title, text=self.text, max_sents=max_sents)
        summary = '\n'.join(summary_sents)
        self.set_summary(summary)

