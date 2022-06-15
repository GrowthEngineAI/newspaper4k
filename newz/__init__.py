import warnings
warnings.filterwarnings('ignore', message='Unclosed')

from .api import (
    build, 
    async_build,
    build_article,
    async_build_article, 
    fulltext, 
    hot, 
    async_hot,
    languages,
    popular_urls, 
    Configuration as Config
)

from .article import Article, ArticleException, AsyncArticle
from .mthreading import NewsPool, AsyncNewsPool
from .source import Source, AsyncSource
from .version import __version__

news_pool = NewsPool()
async_news_pool = AsyncNewsPool()
