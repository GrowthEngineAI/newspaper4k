import anyio
from newz import async_build

async def run_test():

    url = 'https://www.cnn.com'
    #url = 'https://fox13now.com'
    cnn_paper = await async_build(url)

    for article in cnn_paper.articles:
        print(article.url)

    cnn_article = cnn_paper.articles[0]
    await cnn_article.async_build()
    print(cnn_article.text)
    

if __name__ == '__main__':
    anyio.run(run_test)