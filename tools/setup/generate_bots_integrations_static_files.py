#!/usr/bin/env python3
import glob
import os
import shutil
import sys

ZULIP_PATH = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ZULIP_PATH not in sys.path:
    sys.path.append(ZULIP_PATH)
from scripts.lib.setup_path import setup_path

setup_path()

import integrations
from zulip_bots.lib import get_bots_directory_path


def generate_pythonapi_integrations_static_files() -> None:
    integrations_dir = "static/generated/integrations"
    if os.path.isdir(integrations_dir):
        # delete old static files, they could be outdated
        shutil.rmtree(integrations_dir)
    os.makedirs(integrations_dir, exist_ok=True)

    package_integrations_dir = os.path.dirname(os.path.abspath(integrations.__file__))

    def copy_integrations_data(integration_names: list[str]) -> None:
        # The integration name as used in zulip/python-zulip-api.
        for name in integration_names:
            src_dir = os.path.join(package_integrations_dir, name)
            dst_dir = os.path.join(integrations_dir, name)
            doc_path = os.path.join(src_dir, "doc.md")

            if os.path.isfile(doc_path):
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copyfile(doc_path, os.path.join(dst_dir, "doc.md"))

    copy_integrations_data(os.listdir(package_integrations_dir))


def generate_zulip_bots_static_files() -> None:
    bots_dir = "static/generated/bots"
    if os.path.isdir(bots_dir):
        # delete old static files, they could be outdated
        shutil.rmtree(bots_dir)

    os.makedirs(bots_dir, exist_ok=True)

    package_bots_dir = get_bots_directory_path()

    def copy_bots_data(bot_names: list[str]) -> None:
        for name in bot_names:
            src_dir = os.path.join(package_bots_dir, name)
            dst_dir = os.path.join(bots_dir, name)
            doc_path = os.path.join(src_dir, "doc.md")

            if os.path.isfile(doc_path):
                os.makedirs(dst_dir, exist_ok=True)
                shutil.copyfile(doc_path, os.path.join(dst_dir, "doc.md"))

                logo_pattern = os.path.join(src_dir, "logo.*")
                logos = glob.glob(logo_pattern)
                for logo in logos:
                    shutil.copyfile(logo, os.path.join(dst_dir, os.path.basename(logo)))

                assets_path = os.path.join(src_dir, "assets")
                if os.path.isdir(assets_path):
                    shutil.copytree(
                        assets_path, os.path.join(dst_dir, os.path.basename(assets_path))
                    )

    copy_bots_data(os.listdir(package_bots_dir))


if __name__ == "__main__":
    generate_pythonapi_integrations_static_files()
    generate_zulip_bots_static_files()
