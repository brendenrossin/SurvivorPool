#!/usr/bin/env python3
"""
Rate Limiter and Caching for ESPN API to prevent blocking
"""

import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import threading

class APIRateLimiter:
    """
    Thread-safe rate limiter with caching for ESPN API protection
    """

    def __init__(self, max_requests_per_minute: int = 10, cache_duration_seconds: int = 300):
        """
        Initialize rate limiter

        Args:
            max_requests_per_minute: Maximum requests allowed per minute (conservative default)
            cache_duration_seconds: How long to cache API responses (5 minutes default)
        """
        self.max_requests_per_minute = max_requests_per_minute
        self.cache_duration = timedelta(seconds=cache_duration_seconds)

        # Thread-safe tracking
        self._lock = threading.Lock()
        self._request_times = []
        self._cache = {}

        print(f"🛡️  ESPN API Rate Limiter: {max_requests_per_minute} req/min, {cache_duration_seconds}s cache")

    def wait_if_needed(self) -> bool:
        """
        Check if we need to wait before making a request
        Returns True if request can proceed, False if too many requests
        """
        with self._lock:
            now = datetime.now()

            # Remove requests older than 1 minute
            cutoff = now - timedelta(minutes=1)
            self._request_times = [t for t in self._request_times if t > cutoff]

            # Check if we're at the limit
            if len(self._request_times) >= self.max_requests_per_minute:
                oldest_request = min(self._request_times)
                wait_time = 61 - (now - oldest_request).total_seconds()

                if wait_time > 0:
                    print(f"⏳ Rate limit reached. Waiting {wait_time:.1f}s...")
                    time.sleep(wait_time)
                    # Clear the oldest request after waiting
                    self._request_times = self._request_times[1:]

            # Record this request
            self._request_times.append(now)
            return True

    def get_cached_or_fetch(self, cache_key: str, fetch_function, *args, **kwargs) -> Any:
        """
        Get data from cache or fetch fresh data if cache is expired

        Args:
            cache_key: Unique key for this API call
            fetch_function: Function to call if cache miss
            *args, **kwargs: Arguments to pass to fetch_function
        """
        with self._lock:
            # Check cache first
            if cache_key in self._cache:
                cache_entry = self._cache[cache_key]
                if datetime.now() - cache_entry['timestamp'] < self.cache_duration:
                    print(f"📦 Cache hit for: {cache_key}")
                    return cache_entry['data']
                else:
                    print(f"⏰ Cache expired for: {cache_key}")
                    del self._cache[cache_key]

        # Cache miss - need to fetch fresh data
        print(f"🌐 Fetching fresh data for: {cache_key}")

        # Apply rate limiting
        self.wait_if_needed()

        # Fetch fresh data
        try:
            fresh_data = fetch_function(*args, **kwargs)

            # Cache the result
            with self._lock:
                self._cache[cache_key] = {
                    'data': fresh_data,
                    'timestamp': datetime.now()
                }

            return fresh_data

        except Exception as e:
            print(f"❌ Failed to fetch data for {cache_key}: {e}")

            # Try to return stale cache if available
            with self._lock:
                if cache_key in self._cache:
                    print(f"🚨 Returning stale cache for: {cache_key}")
                    return self._cache[cache_key]['data']

            # No cache available, re-raise the exception
            raise

    def clear_cache(self):
        """Clear all cached data"""
        with self._lock:
            self._cache.clear()
            print("🗑️  Cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            now = datetime.now()
            valid_entries = 0
            expired_entries = 0

            for cache_entry in self._cache.values():
                if now - cache_entry['timestamp'] < self.cache_duration:
                    valid_entries += 1
                else:
                    expired_entries += 1

            return {
                'total_entries': len(self._cache),
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'requests_last_minute': len([
                    t for t in self._request_times
                    if now - t < timedelta(minutes=1)
                ])
            }

# Global rate limiter instance
_rate_limiter = None

def get_rate_limiter() -> APIRateLimiter:
    """Get the global rate limiter instance"""
    global _rate_limiter
    if _rate_limiter is None:
        # Conservative defaults to avoid getting blocked
        max_requests = int(os.getenv("ESPN_API_MAX_REQUESTS_PER_MINUTE", "8"))  # Very conservative
        cache_duration = int(os.getenv("ESPN_API_CACHE_DURATION_SECONDS", "300"))  # 5 minutes

        _rate_limiter = APIRateLimiter(max_requests, cache_duration)

    return _rate_limiter