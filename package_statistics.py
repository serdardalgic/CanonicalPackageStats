#!/usr/bin/env python

import argparse
import gzip
import logging
import os
import sys
from collections import defaultdict
from io import BytesIO
from operator import itemgetter
from typing import DefaultDict, Union

import requests

from benchmarking import benchmark_with_repeater

# Set the default base URL as a global variable
DEFAULT_BASE_URL = os.getenv("PACKAGE_MIRROR_URL", "http://ftp.uk.debian.org/debian")


def setup_logging(logfile: str) -> None:
    """Sets up basic logging"""
    logging.basicConfig(
        # Switch to logging.WARN for less logging output
        # level=logging.WARN,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(logfile), logging.StreamHandler()],
    )


def read_gzip_contents(source: Union[str, bytes]) -> str:
    """Reads a gzip file from a file path or bytes, and returns the contents"""
    logging.info("Reading gzip contents")
    try:
        if isinstance(source, str):
            with gzip.open(source, "rt") as f:
                contents = f.read()
        else:
            with gzip.open(BytesIO(source), "rt") as f:
                contents = f.read()
    except gzip.BadGzipFile as e:
        logging.error(f"Bad gzip file {e}")
        sys.exit(1)
    except OSError as e:
        logging.error(f"Error reading gzip file: {e}")
        sys.exit(1)

    logging.info("Successfully read the gzip contents")
    return contents


def download_contents_file(architecture: str, base_url: str) -> bytes:
    """Downloads the Contents file from the Debian mirror"""
    url = f"{base_url}/dists/stable/main/Contents-{architecture}.gz"
    logging.info(f"Downloading Contents file from {url}")
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to download Contents file: {e}")
        raise

    logging.info("Successfully downloaded the Contents file")
    return response.content


def save_contents_file(file_path: str, content: bytes) -> None:
    """Saves the downloaded Contents gzip file locally"""
    with open(file_path, "wb") as f:
        f.write(content)
    logging.info(f"Saved downloaded Contents file as {file_path}")


def read_contents_file(args) -> str:
    """Reads the contents file either from a local cache or by downloading it from the Debian mirror."""
    local_filename = f"Contents-{args.architecture}.gz"
    # If --use-cache is given, check the local gzip file, read it if it exists
    # Otherwise, download the gzip file
    #   - save the gzip file locally if --save-file-locally is given
    #   - read the gzip file
    if args.use_cache:
        if not os.path.isfile(local_filename):
            logging.error(
                f"A file named {local_filename} doesn't exist in the current working directory. "
                "Please run the command with `--save-file-locally` parameter. Exiting..."
            )
            sys.exit(2)
        contents = read_gzip_contents(local_filename)
    else:
        content_bytes = download_contents_file(args.architecture, args.base_url)
        if args.save_file_locally:
            save_contents_file(local_filename, content_bytes)
        contents = read_gzip_contents(content_bytes)

    return contents


def parse_contents(contents: str) -> DefaultDict[str, int]:
    """Parses the Contents file and counts the number of files for each package"""
    logging.info("Parsing the Contents file")
    # defaultdict(int) initializes the default value of new keys to 0
    package_counter: DefaultDict[str, int] = defaultdict(int)
    # split the lines once from the last whitespace, if the lines are non-empty
    file_to_package = [
        line.rsplit(maxsplit=1) for line in contents.splitlines() if line
    ]

    for files, package_list in file_to_package:
        # There can be multiple packages associated with a filepath. Packages are separated by a comma.
        for package in package_list.split(","):
            package_counter[package] += 1

    logging.info("Completed parsing the Contents file")
    return package_counter


def parse_arguments() -> argparse.Namespace:
    """Parses command line arguments"""
    parser = argparse.ArgumentParser(
        description="Statistics of the top 10 Debian packages with most files for a given architecture"
    )
    parser.add_argument(
        "architecture", help="The architecture (e.g., amd64, arm64, mips)"
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="The base URL of the Debian mirror (default: %(default)s)",
    )
    parser.add_argument(
        "-l",
        "--logfile",
        default="package_statistics.log",
        help="Path to the logfile for this script",
    )
    # Mutually exclusive group for --use-cache and --save-file-locally
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--use-cache",
        action="store_true",
        help="Use a cached Contents gzip file in the same directory instead of downloading it",
    )
    group.add_argument(
        "--save-file-locally",
        action="store_true",
        help="Save the downloaded Contents gzip file locally for future use",
    )
    return parser.parse_args()


# @benchmark
@benchmark_with_repeater(repeats=5)
def main():
    args = parse_arguments()

    # Set up logging
    setup_logging(args.logfile)

    # Fetch the contents file and read the contents
    contents = read_contents_file(args)
    # Parse the contents file and count filepaths for the packages
    package_counter = parse_contents(contents)
    # Sort the package_counter dictionary from most files to the least and extract the top 10
    top_packages = sorted(package_counter.items(), key=itemgetter(1), reverse=True)[:10]

    # You can replace print with logging.info or
    #   overwrite the builtin print function with one that uses logging.
    # For simplicity, print is chosen for outputting the package names.
    print("Top 10 packages with the most files:")
    for i, (package_name, file_count) in enumerate(top_packages, 1):
        print(f"{i}. {package_name.ljust(30)} {file_count}")


if __name__ == "__main__":
    main()
