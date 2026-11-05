#!/usr/bin/env python3
"""Protocol Sentinel local developer CLI (not a CI policy or verifier)."""

import argparse
import sys

from sentinel_doctor import main as doctor_main
from sentinel_init import main as init_main


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="sentinel", description="Local developer tools for Protocol Sentinel"
    )
    parser.add_argument("command", choices=("doctor", "init"))
    args, rest = parser.parse_known_args(argv)
    if args.command == "doctor":
        return doctor_main(rest)
    if args.command == "init":
        return init_main(rest)
    return 1


if __name__ == "__main__":
    sys.exit(main())
