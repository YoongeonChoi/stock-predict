import asyncio
import functools
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


async def run_blocking(func: Callable[..., T], /, *args, **kwargs) -> T:
    """Run a blocking function in a worker thread."""
    bound = functools.partial(func, *args, **kwargs)
    return await asyncio.to_thread(bound)


async def gather_limited(
    items: Iterable[T],
    worker: Callable[[T], Awaitable[R]],
    limit: int = 5,
) -> list[R | Exception]:
    """Gather awaitables with bounded concurrency and preserved ordering."""
    semaphore = asyncio.Semaphore(max(1, limit))

    async def _run(item: T) -> R:
        async with semaphore:
            return await worker(item)

    return await asyncio.gather(*(_run(item) for item in items), return_exceptions=True)
