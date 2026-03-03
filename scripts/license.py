"""
Guardian Shield — License Key Validation

Validates license keys against the FAS API.
Caches validation results locally for 30 days to minimize API calls.

License key format: fsg_home_<uuid>

(c) Fallen Angel Systems LLC — All rights reserved.
"""

import os
import json
import hashlib
import time
import logging
import platform
from typing import Optional, Dict

logger = logging.getLogger("guardian-shield.license")

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_CACHE_DIR = os.path.join(os.path.dirname(_SCRIPT_DIR), ".cache")
_CACHE_FILE = os.path.join(_CACHE_DIR, "license_cache.json")
_API_URL = "https://api.fallenangelsystems.com/v2/license/validate"
_CACHE_TTL = 30 * 24 * 3600  # 30 days in seconds


def _machine_hash() -> str:
    """Generate a privacy-safe machine identifier (no PII)."""
    parts = [
        platform.node(),
        platform.machine(),
        platform.system(),
        str(os.getuid()) if hasattr(os, 'getuid') else "0",
    ]
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _load_cache() -> Optional[Dict]:
    """Load cached license validation result."""
    if not os.path.exists(_CACHE_FILE):
        return None

    try:
        with open(_CACHE_FILE, "r") as f:
            cache = json.load(f)

        # Check TTL
        cached_at = cache.get("cached_at", 0)
        if time.time() - cached_at > _CACHE_TTL:
            logger.info("License cache expired")
            return None

        return cache
    except Exception as e:
        logger.warning(f"Failed to load license cache: {e}")
        return None


def _save_cache(result: Dict) -> None:
    """Save license validation result to cache."""
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        result["cached_at"] = time.time()
        with open(_CACHE_FILE, "w") as f:
            json.dump(result, f, indent=2)
    except Exception as e:
        logger.warning(f"Failed to save license cache: {e}")


def _validate_remote(key: str) -> Dict:
    """Validate license key against FAS API."""
    import urllib.request
    import urllib.error

    payload = json.dumps({
        "key": key,
        "machine_hash": _machine_hash(),
    }).encode()

    req = urllib.request.Request(
        _API_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return {
                "valid": data.get("valid", False),
                "tier": data.get("tier", "free"),
                "expiry": data.get("expiry", ""),
                "features": data.get("features", []),
            }
    except urllib.error.HTTPError as e:
        logger.warning(f"License validation HTTP error: {e.code}")
        return {"valid": False, "tier": "free", "error": str(e.code)}
    except Exception as e:
        logger.warning(f"License validation failed: {e}")
        # On network error, fall back to cache if available
        cached = _load_cache()
        if cached and cached.get("valid"):
            logger.info("Using cached license (network unavailable)")
            return cached
        return {"valid": False, "tier": "free", "error": str(e)}


def validate(key: str, force_refresh: bool = False) -> Dict:
    """
    Validate a license key.

    Args:
        key: License key string (format: fsg_home_<uuid>)
        force_refresh: Skip cache and validate against API

    Returns:
        Dict with: valid (bool), tier (str), expiry (str), features (list)
    """
    if not key or not key.startswith("fsg_"):
        return {"valid": False, "tier": "free", "error": "invalid_format"}

    # Check cache first
    if not force_refresh:
        cached = _load_cache()
        if cached and cached.get("key_hash") == hashlib.sha256(key.encode()).hexdigest()[:16]:
            logger.debug("Using cached license validation")
            return cached

    # Validate remotely
    result = _validate_remote(key)
    result["key_hash"] = hashlib.sha256(key.encode()).hexdigest()[:16]

    # Cache successful validations
    if result.get("valid"):
        _save_cache(result)

    return result


def is_licensed(config_path: Optional[str] = None) -> bool:
    """
    Quick check: is the current installation licensed?

    Args:
        config_path: Path to config.json (auto-detected if not provided)

    Returns:
        True if valid license found
    """
    if config_path is None:
        config_path = os.path.join(os.path.dirname(_SCRIPT_DIR), "config.json")

    try:
        with open(config_path, "r") as f:
            config = json.load(f)
        key = config.get("license_key", "")
        if not key:
            return False
        result = validate(key)
        return result.get("valid", False)
    except Exception:
        return False


def clear_cache() -> None:
    """Clear the license validation cache."""
    if os.path.exists(_CACHE_FILE):
        os.remove(_CACHE_FILE)
        logger.info("License cache cleared")
