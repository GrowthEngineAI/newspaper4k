# newspaper4k
 Modified version of [newspaper](https://github.com/codelucas/newspaper) News Extraction with Async Support, focused on performance.

---
Quick Start

```bash
pip install git+https://github.com/GrowthEngineAI/newspaper4k
```

```python

import anyio
from newz import AsyncArticle, async_build

async def test_article():
    url = 'https://github.blog/2022-06-06-introducing-github-skills/'
    article = AsyncArticle(url)

    await article.async_build()
    print('ARTICLE SUMMARY\n', article.summary)

    print('ARTICLE TEXT\n', article.text)
    
async def test_build():
    url = 'https://www.cnn.com'
    cnn_paper = await async_build(url)

    for article in cnn_paper.articles:
        print(article.url)

    cnn_article = cnn_paper.articles[0]
    await cnn_article.async_build()
    print(cnn_article.text)
    

async def run_test():
    await test_article()
    await test_build()
    
if __name__ == '__main__':
    anyio.run(run_test)
```
