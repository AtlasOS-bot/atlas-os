#!/usr/bin/env python3
"""
Atlas web server - generates the value for ATLAS_PASSWORD_HASH.

Run this locally, paste the printed hash into Vercel's environment
variables, and discard the terminal output. The plaintext password is
read via getpass (not echoed, not taken as a command-line argument, so
it never lands in shell history) and is never written to disk or
printed back.

    python scripts/generate_password_hash.py
"""

import getpass
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from server.passwords import hash_password  # noqa: E402


def main():
    password = getpass.getpass("Atlas password: ")
    confirm = getpass.getpass("Confirm password: ")

    if password != confirm:
        print("Passwords did not match - nothing generated.", file=sys.stderr)
        return 1

    if len(password) < 8:
        print("Use at least 8 characters.", file=sys.stderr)
        return 1

    encoded = hash_password(password)
    print()
    print("Set this as the ATLAS_PASSWORD_HASH environment variable in Vercel:")
    print()
    print(encoded)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
