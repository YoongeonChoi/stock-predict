import asyncio
import functools
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeGuard, TypeVar

T = TypeVar("T")
R = TypeVar("R")


class GatheredBaseExceptionError(RuntimeError):
    """Wrap BaseException results from asyncio.gather into a regular Exception."""

    def __init__(self, original: BaseException):
        self.original = original
        detail = str(original).strip()
        message = f"async task failed with {type(original).__name__}"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(message)


def is_async_failure_result(value: object) -> TypeGuard[BaseException]:
    return isinstance(value, BaseException)


def _normalize_gather_result(value: R | BaseException) -> R | Exception:
    if isinstance(value, Exception):
        return value
    if isinstance(value, BaseException):
        return GatheredBaseExceptionError(value)
    return value


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

    gathered = await asyncio.gather(*(_run(item) for item in items), return_exceptions=True)
    return [_normalize_gather_result(item) for item in gathered]
