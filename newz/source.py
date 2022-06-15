
from urllib.parse import urljoin, urlsplit, urlunsplit

from tldextract import tldextract
from typing import List, Union

from . import network
from .article import Article, AsyncArticle
from .configuration import Configuration
from .settings import ANCHOR_DIRECTORY

from .utils import logger as log
from .utils.executor import Executor
from .utils import helpers as utils

import newspaper.urls as urls
from newspaper.extractors import ContentExtractor
from newspaper.source import Source


class Category(object):
    def __init__(self, url):
        self.url = url
        self.html = None
        self.doc = None


class Feed(object):
    def __init__(self, url):
        self.url = url
        self.rss = None
        # TODO self.dom = None, speed up Feedparser


NUM_THREADS_PER_SOURCE_WARN_LIMIT = 5


class AsyncSource(Source):
    """Sources are abstractions of online news vendors like huffpost or cnn.
    domain     =  'www.cnn.com'
    scheme     =  'http'
    categories =  ['http://cnn.com/world', 'http://money.cnn.com']
    feeds      =  ['http://cnn.com/rss.atom', ..]
    articles   =  [<article obj>, <article obj>, ..]
    brand      =  'cnn'
    """
    def __init__(self, url: str, config = None, **kwargs):
        config = config or Configuration()
        super().__init__(url = url, config = config, **kwargs)
    
    async def async_build(self):
        """Encapsulates download and basic parsing with lxml. May be a
        good idea to split this into download() and parse() methods.
        """
        await self.async_download()
        await self.async_parse()

        await self.async_set_categories()
        await self.async_download_categories()  # mthread
        await self.async_parse_categories()
        await self.async_set_feeds()
        await self.async_download_feeds()  # mthread
        # self.parse_feeds()
        await self.async_generate_articles()


    async def async_set_categories(self):
        return await Executor.run_as_async(self.set_categories)

    async def async_set_feeds(self):
        """Don't need to cache getting feed urls, it's almost
        instant with xpath
        """
        common_feed_urls = ['/feed', '/feeds', '/rss']
        common_feed_urls = [urljoin(self.url, url) for url in common_feed_urls]

        split = urlsplit(self.url)
        if split.netloc in ('medium.com', 'www.medium.com'):
            # should handle URL to user or user's post
            if split.path.startswith('/@'):
                new_path = '/feed/' + split.path.split('/')[1]
                new_parts = split.scheme, split.netloc, new_path, '', ''
                common_feed_urls.append(urlunsplit(new_parts))

        common_feed_urls_as_categories = [Category(url=url) for url in common_feed_urls]

        category_urls = [c.url for c in common_feed_urls_as_categories]
        requests = await network.async_multithread_request(category_urls, self.config)
        for index, _ in enumerate(common_feed_urls_as_categories):
            response = requests[index].resp
            if response and response.status_code < 300:
                common_feed_urls_as_categories[index].html = await network.async_get_html(response.url, response=response)
        common_feed_urls_as_categories = [c for c in common_feed_urls_as_categories if c.html]

        for _ in common_feed_urls_as_categories:
            doc = self.config.get_parser().fromstring(_.html)
            _.doc = doc

        common_feed_urls_as_categories = [c for c in common_feed_urls_as_categories if
                                          c.doc is not None]

        categories_and_common_feed_urls = self.categories + common_feed_urls_as_categories
        urls = self.extractor.get_feed_urls(self.url, categories_and_common_feed_urls)
        self.feeds = [Feed(url=url) for url in urls]

    async def async_download(self):
        """Downloads html of source
        """
        self.html = await network.async_get_html(self.url, self.config)
    

    async def async_download_categories(self):
        """Download all category html, can use mthreading
        """
        category_urls = [c.url for c in self.categories]
        requests = await network.async_multithread_request(category_urls, self.config)

        for index, _ in enumerate(self.categories):
            req = requests[index]
            if req.resp is not None:
                self.categories[index].html = await network.async_get_html(req.url, response=req.resp)
            else:
                log.warning(('Deleting category %s from source %s due to '
                             'download error') %
                             (self.categories[index].url, self.url))
        self.categories = [c for c in self.categories if c.html]

    async def async_download_feeds(self):
        """Download all feed html, can use mthreading
        """
        feed_urls = [f.url for f in self.feeds]
        requests = await network.async_multithread_request(feed_urls, self.config)
        for index, _ in enumerate(self.feeds):
            req = requests[index]
            if req.resp is not None:
                self.feeds[index].rss = await network.async_get_html(req.url, response=req.resp)
            else:
                log.warning(('Deleting feed %s from source %s due to '
                             'download error') %
                             (self.categories[index].url, self.url))
        self.feeds = [f for f in self.feeds if f.rss]


    async def async_parse_categories(self):
        return await Executor.run_as_async(self.parse_categories)

    async def async_parse(self):
        """Sets the lxml root, also sets lxml roots of all
        children links, also sets description
        """
        return await Executor.run_as_async(self.parse)


    async def async_feeds_to_articles(self):
        """Returns articles given the url of a feed
        """
        articles = []
        for feed in self.feeds:
            urls = self.extractor.get_urls(feed.rss, regex=True)
            cur_articles = []
            before_purge = len(urls)

            for url in urls:
                article = AsyncArticle(
                    url=url,
                    source_url=feed.url,
                    config=self.config)
                cur_articles.append(article)

            cur_articles = self.purge_articles('url', cur_articles)
            after_purge = len(cur_articles)

            if self.config.memoize_articles:
                cur_articles = utils.memoize_articles(self, cur_articles)
            after_memo = len(cur_articles)

            articles.extend(cur_articles)

            log.debug('%d->%d->%d for %s' %
                      (before_purge, after_purge, after_memo, feed.url))
        return articles

    async def async_categories_to_articles(self):
        """Takes the categories, splays them into a big list of urls and churns
        the articles out of each url with the url_to_article method
        """
        articles = []
        for category in self.categories:
            cur_articles = []
            url_title_tups = self.extractor.get_urls(category.doc, titles=True)
            before_purge = len(url_title_tups)

            for tup in url_title_tups:
                indiv_url = tup[0]
                indiv_title = tup[1]

                _article = AsyncArticle(
                    url=indiv_url,
                    source_url=category.url,
                    title=indiv_title,
                    config=self.config
                )
                cur_articles.append(_article)

            cur_articles = self.purge_articles('url', cur_articles)
            after_purge = len(cur_articles)

            if self.config.memoize_articles:
                cur_articles = utils.memoize_articles(self, cur_articles)
            after_memo = len(cur_articles)

            articles.extend(cur_articles)

            log.debug('%d->%d->%d for %s' %
                      (before_purge, after_purge, after_memo, category.url))
        return articles

    async def _async_generate_articles(self):
        """Returns a list of all articles, from both categories and feeds
        """
        category_articles = await self.async_categories_to_articles()
        feed_articles = await self.async_feeds_to_articles()

        articles = feed_articles + category_articles
        uniq = {article.url: article for article in articles}
        return list(uniq.values())

    async def async_generate_articles(self, limit=5000):
        """Saves all current articles of news source, filter out bad urls
        """
        articles = await self._async_generate_articles()
        self.articles: List[AsyncArticle] = articles[:limit]
        log.debug('%d articles generated and cutoff at %d',
                  len(articles), limit)

    async def async_download_articles(self, threads=1):
        """Downloads all articles attached to self
        """
        # TODO fix how the article's is_downloaded is not set!
        urls = [a.url for a in self.articles]
        failed_articles = []

        if threads == 1:
            for index, article in enumerate(self.articles):
                url = urls[index]
                html = await network.async_get_html(url, config=self.config)
                self.articles[index].set_html(html)
                if not html:
                    failed_articles.append(self.articles[index])
            self.articles = [a for a in self.articles if a.html]
        else:
            if threads > NUM_THREADS_PER_SOURCE_WARN_LIMIT:
                log.warning(('Using %s+ threads on a single source '
                            'may result in rate limiting!') % NUM_THREADS_PER_SOURCE_WARN_LIMIT)
            filled_requests = await network.async_multithread_request(urls, self.config)
            # Note that the responses are returned in original order
            for index, req in enumerate(filled_requests):
                html = await network.async_get_html(req.url, response=req.resp)
                self.articles[index].set_html(html)
                if not req.resp:
                    failed_articles.append(self.articles[index])
            self.articles = [a for a in self.articles if a.html]

        self.is_downloaded = True
        if len(failed_articles) > 0:
            log.warning('The following article urls failed the download: %s' %
                        ', '.join([a.url for a in failed_articles]))

    async def async_parse_articles(self):
        """Parse all articles, delete if too small
        """
        for index, article in enumerate(self.articles):
            await article.async_parse()

        self.articles = self.purge_articles('body', self.articles)
        self.is_parsed = True
