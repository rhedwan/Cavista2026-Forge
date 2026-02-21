# aidcare_pipeline/rate_limiter.py
"""
Rate limiting and caching to protect against high Gemini API usage
"""
import time
import hashlib
import json
from collections import defaultdict
from functools import wraps
from typing import Dict, Any, Optional
import os

# Simple in-memory cache (use Redis in production)
_cache: Dict[str, tuple[Any, float]] = {}
_request_counts: Dict[str, list[float]] = defaultdict(list)

# Configuration
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600"))  # 1 hour default
MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_GEMINI_REQUESTS_PER_MINUTE", "50"))  # Gemini free tier is 60 RPM
MAX_REQUESTS_PER_DAY = int(os.getenv("MAX_GEMINI_REQUESTS_PER_DAY", "1000"))  # Conservative daily limit
ENABLE_CACHING = os.getenv("ENABLE_GEMINI_CACHING", "true").lower() == "true"


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded"""
    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after:.0f} seconds")


def generate_cache_key(func_name: str, *args, **kwargs) -> str:
    """Generate a cache key from function name and arguments"""
    # Create a string representation of the call
    key_data = {
        'func': func_name,
        'args': str(args),
        'kwargs': str(sorted(kwargs.items()))
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()


def check_rate_limit(identifier: str = "global") -> None:
    """
    Check if the rate limit has been exceeded

    Args:
        identifier: Unique identifier for rate limiting (e.g., user_id, ip_address)

    Raises:
        RateLimitExceeded: If rate limit is exceeded
    """
    current_time = time.time()

    # Clean up old entries
    _request_counts[identifier] = [
        t for t in _request_counts[identifier]
        if current_time - t < 86400  # Keep last 24 hours
    ]

    # Check per-minute limit
    recent_requests = [
        t for t in _request_counts[identifier]
        if current_time - t < 60
    ]

    if len(recent_requests) >= MAX_REQUESTS_PER_MINUTE:
        retry_after = 60 - (current_time - recent_requests[0])
        raise RateLimitExceeded(retry_after)

    # Check per-day limit
    if len(_request_counts[identifier]) >= MAX_REQUESTS_PER_DAY:
        oldest_request = _request_counts[identifier][0]
        retry_after = 86400 - (current_time - oldest_request)
        raise RateLimitExceeded(retry_after)

    # Record this request
    _request_counts[identifier].append(current_time)


def get_from_cache(key: str) -> Optional[Any]:
    """Retrieve value from cache if not expired"""
    if not ENABLE_CACHING:
        return None

    if key in _cache:
        value, expiry = _cache[key]
        if time.time() < expiry:
            print(f"Cache HIT for key: {key[:16]}...")
            return value
        else:
            # Expired, remove it
            del _cache[key]
            print(f"Cache EXPIRED for key: {key[:16]}...")

    return None


def set_in_cache(key: str, value: Any, ttl: int = CACHE_TTL_SECONDS) -> None:
    """Store value in cache with TTL"""
    if not ENABLE_CACHING:
        return

    expiry = time.time() + ttl
    _cache[key] = (value, expiry)
    print(f"Cache SET for key: {key[:16]}... (TTL: {ttl}s)")

    # Basic cache size management
    if len(_cache) > 1000:
        # Remove oldest 10% when cache gets too large
        sorted_items = sorted(_cache.items(), key=lambda x: x[1][1])
        for k, _ in sorted_items[:100]:
            del _cache[k]


def cached_gemini_call(ttl: int = CACHE_TTL_SECONDS, rate_limit_id: str = "global"):
    """
    Decorator for Gemini API calls with caching and rate limiting

    Args:
        ttl: Time-to-live for cache in seconds
        rate_limit_id: Identifier for rate limiting
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = generate_cache_key(func.__name__, *args, **kwargs)

            # Try to get from cache first
            cached_result = get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result

            # Check rate limit before making API call
            try:
                check_rate_limit(rate_limit_id)
            except RateLimitExceeded as e:
                print(f"Rate limit exceeded for {func.__name__}: {e}")
                return {
                    "error": f"Rate limit exceeded. Please try again in {e.retry_after:.0f} seconds.",
                    "retry_after": e.retry_after
                }

            # Make the actual API call
            result = func(*args, **kwargs)

            # Only cache successful results (not errors)
            if result and not (isinstance(result, dict) and "error" in result):
                set_in_cache(cache_key, result, ttl)

            return result

        return wrapper
    return decorator


def get_rate_limit_stats(identifier: str = "global") -> Dict[str, Any]:
    """Get current rate limit statistics"""
    current_time = time.time()

    # Clean up old entries
    _request_counts[identifier] = [
        t for t in _request_counts[identifier]
        if current_time - t < 86400
    ]

    recent_requests = [
        t for t in _request_counts[identifier]
        if current_time - t < 60
    ]

    return {
        "requests_last_minute": len(recent_requests),
        "requests_last_day": len(_request_counts[identifier]),
        "max_per_minute": MAX_REQUESTS_PER_MINUTE,
        "max_per_day": MAX_REQUESTS_PER_DAY,
        "cache_enabled": ENABLE_CACHING,
        "cache_size": len(_cache),
        "cache_ttl_seconds": CACHE_TTL_SECONDS
    }


def clear_cache() -> int:
    """Clear all cached entries. Returns number of entries cleared."""
    count = len(_cache)
    _cache.clear()
    print(f"Cache cleared: {count} entries removed")
    return count


def clear_rate_limits(identifier: Optional[str] = None) -> None:
    """Clear rate limit counters for specific identifier or all"""
    if identifier:
        if identifier in _request_counts:
            del _request_counts[identifier]
            print(f"Rate limits cleared for: {identifier}")
    else:
        _request_counts.clear()
        print("All rate limits cleared")
