#!/usr/bin/env python3
"""
Command-line interface for Scanly.
"""

import argparse
import os
import sys

def run_cli():
    """Run the command line interface and return parsed arguments."""
    parser = argparse.ArgumentParser(description="Scanly - Media file scanner and organizer")
    parser.add_argument("path", nargs="?", help="Path to scan")
    parser.add_argument("--movie", "-m", action="store_true", help="Process as movie")
    parser.add_argument("--tv", "-t", action="store_true", help="Process as TV show")
    parser.add_argument("--scan", "-s", action="store_true", help="Scan directory")
    parser.add_argument("--monitor", "-w", action="store_true", help="Monitor directory")
    parser.add_argument("--debug", "-d", action="store_true", help="Enable debug mode")
    parser.add_argument("--version", "-v", action="store_true", help="Show version information")
    
    return parser.parse_args()

if __name__ == "__main__":
    args = run_cli()
    print(args)