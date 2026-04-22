import asyncio
import functools
import time

def retry_async(max_attempts=3, delay=1, backoff=2, exceptions=(Exception,)):
    """
    Decorator for retrying async functions with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            attempts = 0
            current_delay = delay
            while attempts < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    attempts += 1
                    if attempts == max_attempts:
                        print(f"❌ Final attempt failed for {func.__name__}: {e}")
                        raise
                    print(f"⚠️ Attempt {attempts} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            return None
        return wrapper
    return decorator

async def with_timeout(coro, timeout_seconds):
    """
    Runs a coroutine with a timeout.
    """
    try:
        return await asyncio.wait_for(coro, timeout=timeout_seconds)
    except asyncio.TimeoutError:
        print(f"🕒 Timeout reached after {timeout_seconds}s")
        raise
