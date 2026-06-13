#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path


REQUIRED_BACKEND = [
    "API_ENV",
    "API_DATABASE_URL",
    "API_SECRET_KEY",
    "API_BOOTSTRAP_ADMIN_EMAIL",
    "API_BOOTSTRAP_ADMIN_PASSWORD",
    "API_CORS_ORIGINS",
    "API_STORAGE_PATH",
]
REQUIRED_FRONTEND = ["NEXT_PUBLIC_API_BASE_URL"]
PLACEHOLDERS = {
    "API_SECRET_KEY": {"change-me", "change-this-development-secret", "replace-with-long-random-secret"},
    "API_BOOTSTRAP_ADMIN_PASSWORD": {"ChangeMe123!", "replace-with-strong-password"},
}


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def main() -> int:
    parser = argparse.ArgumentParser(description="Check deployment environment values for the free portfolio stack.")
    parser.add_argument("--env-file", default=".env.production.example", help="Env file to read before process env.")
    args = parser.parse_args()

    values = {**load_env_file(Path(args.env_file)), **os.environ}
    errors: list[str] = []

    for key in REQUIRED_BACKEND + REQUIRED_FRONTEND:
        if not values.get(key):
            errors.append(f"{key} is missing")

    if values.get("API_ENV") != "production":
        errors.append("API_ENV should be production for Hugging Face deployment")
    if values.get("API_DATABASE_URL", "").startswith("sqlite"):
        errors.append("API_DATABASE_URL must use PostgreSQL, not SQLite")
    if "sslmode=require" not in values.get("API_DATABASE_URL", ""):
        errors.append("API_DATABASE_URL should include sslmode=require for Neon")
    if values.get("API_STORAGE_PATH") != "/tmp/face-attendance":
        errors.append("API_STORAGE_PATH should be /tmp/face-attendance for Hugging Face free deployment")

    for key, blocked_values in PLACEHOLDERS.items():
        if values.get(key) in blocked_values:
            errors.append(f"{key} is still a placeholder")

    if errors:
        print("Deployment environment check failed:")
        for error in errors:
            print(f"- {error}")
        return 1

    print("Deployment environment check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
