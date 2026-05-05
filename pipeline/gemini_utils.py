"""Shared Gemini API utilities with retry and rate limiting."""

import time
from config import Config

_last_call_time = 0


def rate_limit():
    """Enforce minimum delay between Gemini API calls."""
    global _last_call_time
    now = time.time()
    elapsed = now - _last_call_time
    if elapsed < Config.GEMINI_CALL_DELAY:
        time.sleep(Config.GEMINI_CALL_DELAY - elapsed)
    _last_call_time = time.time()


def call_gemini(client, model, contents, config=None):
    """Call Gemini API with retry, backoff, and rate limiting.

    Returns the response object on success, or None on failure.
    """
    from google.genai import types

    rate_limit()

    last_error = None
    for attempt in range(Config.GEMINI_RETRY_MAX):
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            return response
        except Exception as e:
            last_error = e
            error_str = str(e)
            # Retry on rate limit or server errors
            if "429" in error_str or "503" in error_str or "UNAVAILABLE" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                wait = Config.GEMINI_RETRY_BACKOFF ** (attempt + 1)
                print(f"  API rate limit/server error (attempt {attempt + 1}/{Config.GEMINI_RETRY_MAX}), waiting {wait:.0f}s...")
                time.sleep(wait)
            else:
                # Non-retryable error
                print(f"  Gemini API error: {error_str[:200]}")
                return None

    print(f"  Gemini API failed after {Config.GEMINI_RETRY_MAX} retries: {str(last_error)[:200]}")
    return None
