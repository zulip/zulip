import os
import subprocess
import time
from pathlib import Path
from typing import List

import digitalocean
import zulip
from requests.adapters import HTTPAdapter
from urllib3.util import Retry

manager = digitalocean.Manager(token=os.environ["DIGITALOCEAN_API_KEY"])
# We just temporarily create the client now, to validate that we can
# auth to the server; reusing it after the whole install fails because
# the connection has been half-closed in a way that breaks it.
zulip.Client()
TEST_DROPLET_SUBDOMAIN = "do"


def generate_ssh_keys() -> None:
    subprocess.check_call(
        ["ssh-keygen", "-f", str(Path.home()) + "/.ssh/id_ed25519", "-P", "", "-t", "ed25519"]
    )


def get_public_ssh_key() -> str:
    try:
        with open(str(Path.home()) + "/.ssh/id_ed25519.pub") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def sleep_until_droplet_action_is_completed(
    droplet: digitalocean.Droplet, action_type: str
) -> None:
    incomplete = True
    while incomplete:
        for action in droplet.get_actions():
            action.load()
            print(f"...[{action.type}]: {action.status}")
            if action.type == action_type and action.status == "completed":
                incomplete = False
                break
        if incomplete:
            time.sleep(5)

    # Sometimes the droplet does not yet have an .ip_address value
    # (the attribute is None) after .load()ing the droplet. We cannot
    # proceed without the IP, so we wait in a loop until the IP is
    # returned to us.
    while True:
        droplet.load()
        if droplet.ip_address:
            break
        time.sleep(5)


def set_api_request_retry_limits(api_object: digitalocean.baseapi.BaseAPI) -> None:
    retry = Retry(connect=5, read=5, backoff_factor=0.1)
    adapter = HTTPAdapter(max_retries=retry)
    api_object._session.mount("https://", adapter)


def create_droplet(
    name: str, ssh_keys: List[str], image: str = "ubuntu-20-04-x64"
) -> digitalocean.Droplet:
    droplet = digitalocean.Droplet(
        token=manager.token,
        name=name,
        region="nyc3",
        size_slug="s-1vcpu-2gb",
        image=image,
        backups=False,
        ssh_keys=ssh_keys,
        tags=["github-action", "temporary"],
    )
    set_api_request_retry_limits(droplet)
    droplet.create()
    sleep_until_droplet_action_is_completed(droplet, "create")
    return droplet


def create_ssh_key(name: str, public_key: str) -> digitalocean.SSHKey:
    action_public_ssh_key_object = digitalocean.SSHKey(
        name=name, public_key=public_key, token=manager.token
    )
    set_api_request_retry_limits(action_public_ssh_key_object)
    action_public_ssh_key_object.create()
    return action_public_ssh_key_object


def create_snapshot(droplet: digitalocean.Droplet, snapshot_name: str) -> None:
    droplet.take_snapshot(snapshot_name, power_off=True)
    droplet.load()
    sleep_until_droplet_action_is_completed(droplet, "snapshot")


def create_dns_records(droplet: digitalocean.Droplet) -> None:
    domain = digitalocean.Domain(token=manager.token, name="oneclick.zulip.dev")
    set_api_request_retry_limits(domain)
    domain.load()

    oneclick_test_app_record_names = [TEST_DROPLET_SUBDOMAIN, f"*.{TEST_DROPLET_SUBDOMAIN}"]
    for record in domain.get_records():
        if (
            record.name in oneclick_test_app_record_names
            and record.domain == "oneclick.zulip.dev"
            and record.type == "A"
        ):
            record.destroy()

    domain.load()
    for record_name in oneclick_test_app_record_names:
        domain.create_new_domain_record(type="A", name=record_name, data=droplet.ip_address)


def setup_one_click_app_installer(droplet: digitalocean.Droplet) -> None:
    subprocess.check_call(
        [
            "fab",
            "build_image",
            "-H",
            droplet.ip_address,
            "--keepalive",
            "5",
            "--connection-attempts",
            "10",
        ],
        cwd="marketplace-partners/marketplace_docs/templates/Fabric",
    )


def send_message(content: str) -> None:
    request = {
        "type": "stream",
        "to": os.environ["ONE_CLICK_ACTION_STREAM"],
        "topic": "digitalocean installer",
        "content": content,
    }
    zulip.Client().send_message(request)


if __name__ == "__main__":
    release_version = os.environ["RELEASE_VERSION"]

    generate_ssh_keys()
    action_public_ssh_key_object = create_ssh_key(
        f"oneclickapp-{release_version}-image-generator-public-key", get_public_ssh_key()
    )

    image_generator_droplet = create_droplet(
        f"oneclickapp-{release_version}-image-generator", [action_public_ssh_key_object]
    )

    setup_one_click_app_installer(image_generator_droplet)

    oneclick_image_name = f"oneclickapp-{release_version}"
    create_snapshot(image_generator_droplet, oneclick_image_name)
    snapshot = image_generator_droplet.get_snapshots()[0]
    send_message(f"One click app image `{oneclick_image_name}` created.")

    image_generator_droplet.destroy()
    action_public_ssh_key_object.destroy()

    test_droplet_name = f"oneclickapp-{release_version}-test"
    test_droplet = create_droplet(test_droplet_name, manager.get_all_sshkeys(), image=snapshot.id)
    create_dns_records(test_droplet)
    send_message(
        f"Test droplet `{test_droplet_name}` created. SSH as root to {TEST_DROPLET_SUBDOMAIN}.oneclick.zulip.dev for testing."
    )
