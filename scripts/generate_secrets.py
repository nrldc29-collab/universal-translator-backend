#!/usr/bin/env python3
"""
Generate strong secrets for production deployment.

Run this script to generate secure random secrets for:
- JWT_SECRET (translator backend)
- STT_PROVIDER_API_KEY (translator backend -> STT provider)
- STT_API_KEY (STT provider)
- ADMIN_API_KEY (STT provider)

Usage:
    python scripts/generate_secrets.py

Output:
    Prints .env-compatible key=value pairs.
"""
import secrets
import sys


def generate_secret(length_bytes: int = 48) -> str:
    """Generate a URL-safe random secret."""
    return secrets.token_urlsafe(length_bytes)


def main() -> None:
    print("# Production secrets - copy these to your .env files")
    print("#")
    print("# Translator backend (.env):")
    print(f"JWT_SECRET={generate_secret()}")
    print(f"STT_PROVIDER_API_KEY={generate_secret()}")
    print()
    print("# STT provider (stt_provider/.env):")
    print(f"STT_API_KEY={generate_secret()}")
    print(f"ADMIN_API_KEY={generate_secret()}")
    print()
    print("# IMPORTANT: When using streaming STT, set STT_API_KEYS in provider to:")
    print("# STT_API_KEYS=translator:<same-value-as-STT_PROVIDER_API_KEY-above>")
    print()
    print("# Example STT_API_KEYS:")
    stt_api_key = generate_secret()
    print(f"STT_API_KEYS=translator:{stt_api_key},browser:{stt_api_key}")
    print()
    print("# Then set translator backend STT_PROVIDER_API_KEY to:")
    print(f"STT_PROVIDER_API_KEY={stt_api_key}")


if __name__ == "__main__":
    main()
