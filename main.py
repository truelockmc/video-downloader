#!/usr/bin/env python3
"""
Entrypoint: starts GUI from gui.py
Simple Wrapper Script
"""
import sys
import argparse

from gui import main_app

def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cli", "-c", action="store_true", help="Start interactive CLI mode")
    # These arguments are forwarded to the CLI handler when --cli is set.
    parser.add_argument("--resolution", "-r")
    parser.add_argument("--bitrate", "-b")
    parser.add_argument("--format", "-f")
    parser.add_argument("--filename", "-n")
    parser.add_argument("--folder", "-d")
    parser.add_argument("--ytdlp-args", "-a", nargs="*", help="Raw yt-dlp arguments (may be a quoted string)")
    parser.add_argument("url", nargs="?", help="Optional URL (relevant only in CLI mode)")
    args, remaining = parser.parse_known_args()

    if args.cli:
        from cli import run_cli
        cli_argv = sys.argv[1:]
        rc = run_cli(cli_argv)
        sys.exit(rc)
    else:
        main_app()

if __name__ == "__main__":
    main()
