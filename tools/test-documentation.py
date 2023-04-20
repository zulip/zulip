#!/usr/bin/env python3


"""
This script tests the Zulip documentation by performing the following steps:

1. Checks if the user's development environment is set up correctly by running the provision script.
2. Checks if Sphinx is installed and available on the system.
3. Validates the HTML using vnu.jar.
4. Tests the links in the documentation.
5. Runs the Zulip test suite.

The script takes the following optional arguments:
    --loglevel LEVEL: set the log level (default: ERROR)
    --skip-check-links: skip checking of links
    --skip-external-links: skip checking of external links

Usage: ./tools/test-documentation.py [OPTIONS]

"""

import argparse
import os
import subprocess
import sys

def color_message(color_code, message):
    """Prints the message in the given color code."""
    print(f"\033[{color_code}m{message}\033[0m")

def run_command(command):
    """Runs the given command and returns the exit code."""
    result = subprocess.run(command, shell=True, capture_output=True)
    print(result.stdout.decode())
    print(result.stderr.decode())
    return result.returncode

def check_sphinx():
    """Checks if Sphinx is installed and available on the system."""
    try:
        subprocess.check_call(["sphinx-build", "--version"])
    except subprocess.CalledProcessError:
        color_message("91", "Sphinx is not installed or not on PATH. Please install it before continuing.")
        sys.exit(1)

def validate_html():
    """Validates the HTML using vnu.jar."""
    color_message("94", "Validating HTML...")
    command = (
        "java -jar ../node_modules/vnu-jar/build/dist/vnu.jar "
        "--filterfile ../tools/documentation.vnufilter "
        "--skip-non-html _build/html"
    )
    return run_command(command)

def test_links(skip_external_links):
    """Tests the links in the documentation."""
    color_message("94", "Testing links in documentation...")
    command = (
        "scrapy crawl_with_status documentation_crawler "
        f"{'' if not skip_external_links else '-a skip_external=set'}"
    )
    return run_command(command)

def run_test_suite():
    """Runs the Zulip test suite."""
    color_message("94", "Running Zulip test suite...")
    command = "tools/run-dev.py test-backend"
    return run_command(command)

def check_environment():
    """Checks if the user's development environment is set up correctly"""
    try:
        subprocess.check_call(["../tools/provision", "--help"])
    except subprocess.CalledProcessError:
        color_message("91", "Your development environment is not set up correctly. Please run `./tools/provision` to set it up.")
        sys.exit(1)

def main():
    """Main function that runs the test script."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--loglevel", "-L", metavar="LEVEL",
        help="log level (default: ERROR)", default="ERROR"
    )
    parser.add_argument(
        "--skip-check-links", action="store_true",
        help="skip checking of links"
    )
    parser.add_argument(
        "--skip-external-links", action="store_true",
        help="skip checking of external links"
    )
    args = parser.parse_args()

    os.chdir(os.path.join(os.path.dirname(__file__), "..", "docs"))

    check_environment()
    check_sphinx()
    validate_html()

    if not args.skip_check_links:
        test_links(args.skip_external_links)

    run_test_suite()

if __name__ == "__main__":
    main()
