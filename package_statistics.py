#!/usr/bin/env python

import argparse
import gzip
import logging
import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from operator import itemgetter
from typing import DefaultDict, Iterator, List, Union

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


def read_gzip_contents(source: Union[str, bytes]) -> Iterator[str]:
    """Reads and decompresses a gzip file from a file path or bytes line by line"""
    logging.info("Reading gzip contents")
    try:
        if isinstance(source, str):
            with gzip.open(source, "rt") as f:
                for line in f:
                    yield line
        else:
            with gzip.open(BytesIO(source), "rt") as f:
                for line in f:
                    yield line

    except gzip.BadGzipFile as e:
        logging.error(f"Bad gzip file {e}")
        sys.exit(1)
    except OSError as e:
        logging.error(f"Error reading gzip file: {e}")
        sys.exit(1)

    logging.info("Successfully read the gzip contents")


def download_contents_file(architecture: str, base_url: str) -> bytes:
    """Downloads the Contents file from the Debian mirror"""
    url = f"{base_url}/dists/stable/main/Contents-{architecture}.gz"
    logging.info(f"Downloading Contents file from {url}")
    try:
        response = requests.get(url, timeout=30, stream=True)
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


def read_contents_file(args) -> Iterator[str]:
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
        return read_gzip_contents(local_filename)
    else:
        content_bytes = download_contents_file(args.architecture, args.base_url)
        if args.save_file_locally:
            save_contents_file(local_filename, content_bytes)
        return read_gzip_contents(content_bytes)


def process_chunk(lines: List[str]) -> DefaultDict[str, int]:
    """Processes a chunk of lines and returns the package count"""
    package_counter: DefaultDict[str, int] = defaultdict(int)
    for line in lines:
        if not line.strip():
            continue
        try:
            file_path, package_names = line.rsplit(maxsplit=1)
            for package_name in package_names.strip().split(","):
                package_counter[package_name] += 1
        except ValueError:
            logging.error(f"Failed to parse line: {line.strip()}")
    return package_counter


def parse_contents(
    lines: Iterator[str], chunk_size: int = 1000
) -> DefaultDict[str, int]:
    """Parses the Contents file and counts the number of files for each package using multithreading"""
    logging.info("Parsing the Contents file")
    package_counter: DefaultDict[str, int] = defaultdict(int)
    chunks = []
    current_chunk = []

    for line in lines:
        current_chunk.append(line)
        if len(current_chunk) >= chunk_size:
            chunks.append(current_chunk)
            current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(process_chunk, chunk) for chunk in chunks]
        for future in futures:
            result = future.result()
            for package_name, count in result.items():
                package_counter[package_name] += count

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

    # Fetch the contents file and read the contents by yielding line by line
    lines = read_contents_file(args)
    # Parse the contents file and count filepaths for the packages
    package_counter = parse_contents(lines)
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
