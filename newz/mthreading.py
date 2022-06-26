# -*- coding: utf-8 -*-
"""
Anything that has to do with threading in this library
must be abstracted in this file. If we decide to do gevent
also, it will deserve its own gevent file.
"""

import queue
import traceback
import asyncio

from threading import Thread
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from .article import AsyncArticle
from .configuration import Configuration

from .utils.executor import Executor
from .utils import logger as log

from newspaper.mthreading import NewsPool

class ConcurrencyException(Exception):
    pass


class Worker(Thread):
    """
    Thread executing tasks from a given tasks queue.
    """
    def __init__(self, tasks, timeout_seconds):
        Thread.__init__(self)
        self.tasks = tasks
        self.timeout = timeout_seconds
        self.daemon = True
        self.start()

    def run(self):
        while True:
            try:
                func, args, kargs = self.tasks.get(timeout=self.timeout)
            except queue.Empty:
                # Extra thread allocated, no job, exit gracefully
                break
            try:
                func(*args, **kargs)
            except Exception:
                traceback.print_exc()

            self.tasks.task_done()


class ThreadPool:
    def __init__(self, num_threads, timeout_seconds):
        self.tasks = queue.Queue(num_threads)
        for _ in range(num_threads):
            Worker(self.tasks, timeout_seconds)

    def add_task(self, func, *args, **kargs):
        self.tasks.put((func, args, kargs))

    def wait_completion(self):
        self.tasks.join()


class AsyncNewsPool(object):

    def __init__(self, config=None):
        """
        Abstraction of a threadpool. A newspool can accept any number of
        source OR article objects together in a list. It allocates one
        thread to every source and then joins.

        We allocate one thread per source to avoid rate limiting.
        5 sources = 5 threads, one per source.

        >>> import newz
        >>> from newz import news_pool

        >>> cnn_paper = await newz.async_build('http://cnn.com')
        >>> tc_paper = await newz.async_build('http://techcrunch.com')
        >>> espn_paper = await newz.async_build('http://espn.com')

        >>> papers = [cnn_paper, tc_paper, espn_paper]
        >>> news_pool.set(papers)
        >>> news_pool.join()

        # All of your papers should have their articles html all populated now.
        >>> cnn_paper.articles[50].html
        u'<html>blahblah ... '
        """
        self.pool = None
        self.futures = []
        self.config = config or Configuration()

    async def async_join(self):
        """
        Runs the mtheading and returns when all threads have joined
        resets the task.
        """
        if not self.futures:
            raise ConcurrencyException('Call async_set(..) with a list of source objects '
                                       'before calling .async_join(..)')
        await asyncio.gather(*self.futures)
        self.futures = []


    def join(self):
        """
        Runs the mtheading and returns when all threads have joined
        resets the task.
        """
        if self.pool is None:
            raise ConcurrencyException('Call set(..) with a list of source objects '
                                       'before calling .join(..)')
        self.pool.wait_completion()
        self.pool = None
    

    async def async_set(self, news_list, threads_per_source: int = 1, override_threads=None):
        """
        news_list can be a list of `Article`, `Source`, or both.

        If caller wants to decide how many threads to use, they can use
        `override_threads` which takes precedence over all. Otherwise,
        this api infers that if the input is all `Source` objects, to
        allocate one thread per `Source` to not spam the host.

        If both of the above conditions are not true, default to 1 thread.
        """
        from .source import AsyncSource, Source

        if override_threads is not None:
            num_threads = override_threads
        elif all([isinstance(n, AsyncSource) for n in news_list]):
            num_threads = threads_per_source * len(news_list)
        else:
            num_threads = 1

        timeout = self.config.thread_timeout_seconds
        #self.pool = ThreadPool(num_threads, timeout)
        #self.pool = ThreadPoolExecutor(num_threads)
        # ProcessPool is faster than ThreadPool
        self.pool = ProcessPoolExecutor(num_threads)
        
        loop = asyncio.get_running_loop()

        for news_object in news_list:
            if isinstance(news_object, AsyncSource):
                self.futures.append(
                    loop.run_in_executor(
                        self.pool.submit(news_object.async_download_articles),
                    )
                )
                #self.pool.add_task(news_object.download_articles)
            elif isinstance(news_object, Source):
                self.futures.append(
                    loop.run_in_executor(
                        self.pool.submit(news_object.download_articles),
                    )
                )
                #self.pool.add_task(news_object.download_articles)
            
            elif isinstance(news_object, AsyncArticle):
                self.futures.append(
                    loop.run_in_executor(
                        self.pool.submit(news_object.async_download),
                    )
                )
                #self.pool.add_task(news_object.async_download)
            else:
                self.futures.append(
                    loop.run_in_executor(
                        self.pool.submit(news_object.download),
                    )
                )
                #self.pool.add_task(news_object.download)

    def set(self, news_list, threads_per_source=1, override_threads=None):
        """
        news_list can be a list of `Article`, `Source`, or both.

        If caller wants to decide how many threads to use, they can use
        `override_threads` which takes precedence over all. Otherwise,
        this api infers that if the input is all `Source` objects, to
        allocate one thread per `Source` to not spam the host.

        If both of the above conditions are not true, default to 1 thread.
        """
        from .source import Source

        if override_threads is not None:
            num_threads = override_threads
        elif all([isinstance(n, Source) for n in news_list]):
            num_threads = threads_per_source * len(news_list)
        else:
            num_threads = 1

        timeout = self.config.thread_timeout_seconds
        self.pool = ThreadPool(num_threads, timeout)

        for news_object in news_list:
            if isinstance(news_object, Source):
                self.pool.add_task(news_object.download_articles)
            else:
                self.pool.add_task(news_object.download)
