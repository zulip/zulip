#!/usr/bin/env python3
"""
Register commands for the test advanced bot.

This script registers bot commands using the Zulip API.
It must be run as the bot user (using the bot's API key).

Usage:
    python register_test_bot_commands.py --bot-email testbot-bot@zulipdev.com --api-key <bot-api-key>

Or configure ZULIP_BOT_EMAIL and ZULIP_BOT_API_KEY environment variables.
"""

import argparse
import os
import sys

import requests

# Command definitions matching test_advanced_bot.py
BOT_COMMANDS = [
    {
        "name": "testbot",
        "description": "Run bot widget tests",
        "options": [
            {
                "name": "test",
                "type": "string",
                "description": "Which test to run",
                "required": True,
                "choices": [
                    {"name": "Rich Embed (Basic)", "value": "embed_basic"},
                    {"name": "Rich Embed (Full)", "value": "embed_full"},
                    {"name": "Buttons (All Styles)", "value": "buttons"},
                    {"name": "Approval Workflow", "value": "approval"},
                    {"name": "Select Menus", "value": "select"},
                    {"name": "Modals", "value": "modal"},
                    {"name": "Freeform Counter", "value": "freeform_counter"},
                    {"name": "Freeform Poll", "value": "freeform_poll"},
                    {"name": "All Widgets", "value": "all"},
                ],
            }
        ],
    },
    {
        "name": "weather",
        "description": "Get weather for a location",
        "options": [
            {
                "name": "location",
                "type": "string",
                "description": "City name or ZIP code",
                "required": True,
            },
            {
                "name": "units",
                "type": "string",
                "description": "Temperature units",
                "choices": [
                    {"name": "Celsius", "value": "c"},
                    {"name": "Fahrenheit", "value": "f"},
                ],
            },
        ],
    },
    {
        "name": "inventory",
        "description": "Search inventory items (with autocomplete)",
        "options": [
            {
                "name": "item",
                "type": "string",
                "description": "Item to search",
                "required": True,
            }
        ],
    },
    {
        "name": "echo",
        "description": "Echo back a message with response type",
        "options": [
            {
                "name": "message",
                "type": "string",
                "description": "Message to echo",
                "required": True,
            },
            {
                "name": "type",
                "type": "string",
                "description": "Response type",
                "choices": [
                    {"name": "Public", "value": "public"},
                    {"name": "Ephemeral (only you)", "value": "ephemeral"},
                    {"name": "With Widget", "value": "widget"},
                ],
            },
        ],
    },
]


def register_commands(site_url: str, bot_email: str, api_key: str) -> bool:
    """Register all bot commands with the Zulip server."""
    session = requests.Session()
    session.auth = (bot_email, api_key)

    success = True
    for command in BOT_COMMANDS:
        print(f"Registering command: /{command['name']}...")

        response = session.post(
            f"{site_url}/api/v1/bot_commands",
            json={
                "name": command["name"],
                "description": command["description"],
                "options": command.get("options", []),
            },
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("created"):
                print(f"  Created new command /{command['name']}")
            else:
                print(f"  Updated existing command /{command['name']}")
        else:
            print(f"  ERROR: {response.status_code} - {response.text}")
            success = False

    return success


def main():
    parser = argparse.ArgumentParser(description="Register bot commands with Zulip")
    parser.add_argument(
        "--site",
        default=os.environ.get("ZULIP_SITE", "http://localhost:9991"),
        help="Zulip site URL (default: http://localhost:9991)",
    )
    parser.add_argument(
        "--bot-email",
        default=os.environ.get("ZULIP_BOT_EMAIL"),
        help="Bot email address",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("ZULIP_BOT_API_KEY"),
        help="Bot API key",
    )

    args = parser.parse_args()

    if not args.bot_email:
        print("ERROR: Bot email required. Use --bot-email or ZULIP_BOT_EMAIL env var.")
        sys.exit(1)

    if not args.api_key:
        print("ERROR: API key required. Use --api-key or ZULIP_BOT_API_KEY env var.")
        sys.exit(1)

    print(f"Registering commands at {args.site} as {args.bot_email}")
    print()

    if register_commands(args.site, args.bot_email, args.api_key):
        print()
        print("All commands registered successfully!")
        print()
        print("Now start the test bot server:")
        print("  python test_advanced_bot.py")
    else:
        print()
        print("Some commands failed to register.")
        sys.exit(1)


if __name__ == "__main__":
    main()
