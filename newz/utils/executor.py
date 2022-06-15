
import anyio
import asyncio
import functools

from concurrent import futures
from anyio._core._eventloop import threadlocals
from typing import List, Union, Callable, Coroutine, Any

from .helpers import is_coro_func

class Executor:
    pool: futures.ThreadPoolExecutor = None

    @staticmethod
    def is_coro(func: Union[Callable, Coroutine, Any], func_name: str = None) -> bool:
        return is_coro_func(func, func_name)

    @classmethod
    def init_pool(cls):
        if cls.pool: return
        cls.pool = futures.ThreadPoolExecutor(max_workers = 8)
    
    @classmethod
    def get_pool(cls) -> futures.ThreadPoolExecutor:
        cls.init_pool()
        return cls.pool

    @classmethod
    def get_async_module(cls):
        return getattr(threadlocals, "current_async_module", None)

    @classmethod
    async def run_as_async(cls, sync_func: Callable, *args, **kwargs):
        """
        Turns a Sync Function into an Async Function        
        """
        blocking = functools.partial(sync_func, *args, **kwargs)
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(cls.get_pool(), blocking)
    
    @classmethod
    def run_as_sync(cls, async_func: Coroutine, *args, **kwargs):
        """
        Turns an Async Function into a Sync Function
        """
        current_async_module = cls.get_async_module()
        partial_f = functools.partial(async_func, *args, **kwargs)
        if current_async_module is None:
            return anyio.run(partial_f)
        return anyio.from_thread.run(partial_f)
