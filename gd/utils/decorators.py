import asyncio
import functools
import inspect
import time

from . import maybe_coroutine

from ..typing import Any, Callable, Type, TypeVar
from ..errors import NotLoggedError, MissingAccess

Function = Callable[[Any], Any]

__all__ = ("check_logged", "check_logged_obj", "benchmark", "impl_sync", "source", "sync", "run_once")

T = TypeVar("T")


def check_logged(func: Function) -> Function:
    # decorator that checks if passed client is logged in.
    @functools.wraps(func)
    def wrapper(obj: Any, *args, **kwargs) -> Any:
        # apply actual check
        check_logged_obj(obj, func.__name__)

        return func(obj, *args, **kwargs)

    return wrapper


def check_logged_obj(obj: Any, func_name: str) -> None:
    try:
        client = obj if hasattr(obj, "is_logged") else obj.client

    except AttributeError:
        raise MissingAccess(message=f"Failed to find client on object: {obj!r}.") from None

    else:
        if client is None:
            raise MissingAccess(
                message=(
                    f"Attempt to check if client is logged for {obj!r} returned None. "
                    "Have you made this object by hand?"
                )
            )

        if not client.is_logged():
            raise NotLoggedError(func_name)


def source(func: Function) -> Function:
    try:
        print(inspect.getsource(func))
    except Exception:
        pass

    @functools.wraps(func)
    def decorator(*args, **kwargs) -> Any:
        return func(*args, **kwargs)

    return decorator


def benchmark(func: Function) -> Function:
    @functools.wraps(func)
    def decorator(*args, **kwargs) -> Any:

        start = time.perf_counter()
        res = func(*args, **kwargs)
        end = time.perf_counter()

        time_taken = (end - start) * 1000

        print(f"Executed {func!r}\nEstimated time: {time_taken:,.2f}ms.")

        return res

    return decorator


def sync(func: Function) -> Function:
    @functools.wraps(func)
    def syncer(*args, **kwargs) -> Any:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        return loop.run_until_complete(maybe_coroutine(func, *args, **kwargs))  # no shutdown uwu ~ nekit

    return syncer


def impl_sync(cls: Type[T]) -> Type[T]:
    try:
        old_get = cls.__getattr__
    except AttributeError:
        def old_get(instance: Any, name: str) -> None:
            raise AttributeError(f"{type(instance).__name__!r} has no attribute {name!r}")

    lookup = "sync_"

    def get_impl(instance: Any, name: str) -> Any:
        if name.startswith(lookup):
            name = name[len(lookup):]  # skip lookup part in name

            return sync(getattr(instance, name))

        else:
            return old_get(instance, name)

    cls.__getattr__ = get_impl

    return cls


def run_once(func: Function) -> Function:
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:

        if not hasattr(func, "_res"):
            func._res = func(*args, **kwargs)

        return func._res

    return wrapper
