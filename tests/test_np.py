import anyio
from newz import async_news_pool

async def run_test():
    url = 'https://blog.finxter.com/python-__aenter__-magic-method/'
    article = AsyncArticle(url)
    await article.async_build()
    print(article.text)
    print(article.summary)
    

if __name__ == '__main__':
    anyio.run(run_test)