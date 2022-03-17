#!/usr/bin/env python3
import argparse
import asyncio
import os
import pwd
import signal
import subprocess
import sys
from typing import List, Sequence
from urllib.parse import urlunparse

TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(TOOLS_DIR))

# check for the venv
from tools.lib import sanity_check

sanity_check.check_venv(__file__)

from tornado import httpclient, httputil, web
from tornado.platform.asyncio import AsyncIOMainLoop

from tools.lib.test_script import add_provision_check_override_param, assert_provisioning_status_ok

if "posix" in os.name and os.geteuid() == 0:
    raise RuntimeError("run-dev.py should not be run as root.")

DESCRIPTION = """
Starts the app listening on localhost, for local development.

This script launches the Django and Tornado servers, then runs a reverse proxy
which serves to both of them.  After it's all up and running, browse to

    http://localhost:9991/

Note that, while runserver and runtornado have the usual auto-restarting
behavior, the reverse proxy itself does *not* automatically restart on changes
to this file.
"""

parser = argparse.ArgumentParser(
    description=DESCRIPTION, formatter_class=argparse.RawTextHelpFormatter
)

parser.add_argument("--test", action="store_true", help="Use the testing database and ports")
parser.add_argument("--minify", action="store_true", help="Minifies assets for testing in dev")
parser.add_argument("--interface", help="Set the IP or hostname for the proxy to listen on")
parser.add_argument(
    "--no-clear-memcached",
    action="store_false",
    dest="clear_memcached",
    help="Do not clear memcached on startup",
)
parser.add_argument("--streamlined", action="store_true", help="Avoid process_queue, etc.")
parser.add_argument(
    "--enable-tornado-logging",
    action="store_true",
    help="Enable access logs from tornado proxy server.",
)
add_provision_check_override_param(parser)
options = parser.parse_args()

assert_provisioning_status_ok(options.skip_provision_check)

if options.interface is None:
    user_id = os.getuid()
    user_name = pwd.getpwuid(user_id).pw_name
    if user_name in ["vagrant", "zulipdev"]:
        # In the Vagrant development environment, we need to listen on
        # all ports, and it's safe to do so, because Vagrant is only
        # exposing certain guest ports (by default just 9991) to the
        # host.  The same argument applies to the remote development
        # servers using username "zulipdev".
        options.interface = None
    else:
        # Otherwise, only listen to requests on localhost for security.
        options.interface = "127.0.0.1"
elif options.interface == "":
    options.interface = None

runserver_args: List[str] = []
base_port = 9991
if options.test:
    base_port = 9981
    settings_module = "zproject.test_settings"
    # Don't auto-reload when running Puppeteer tests
    runserver_args = ["--noreload"]
    tornado_autoreload = []
else:
    settings_module = "zproject.settings"
    tornado_autoreload = ["-m", "tornado.autoreload"]

manage_args = [f"--settings={settings_module}"]
os.environ["DJANGO_SETTINGS_MODULE"] = settings_module

from scripts.lib.zulip_tools import CYAN, ENDC

proxy_port = base_port
django_port = base_port + 1
tornado_port = base_port + 2
webpack_port = base_port + 3

os.chdir(os.path.join(os.path.dirname(__file__), ".."))

if options.clear_memcached:
    subprocess.check_call("./scripts/setup/flush-memcached")

# Set up a new process group, so that we can later kill run{server,tornado}
# and all of the processes they spawn.
os.setpgrp()

# Save pid of parent process to the pid file. It can be used later by
# tools/stop-run-dev to kill the server without having to find the
# terminal in question.

if options.test:
    pid_file_path = os.path.join(os.path.join(os.getcwd(), "var/puppeteer/run_dev.pid"))
else:
    pid_file_path = os.path.join(os.path.join(os.getcwd(), "var/run/run_dev.pid"))

# Required for compatibility python versions.
if not os.path.exists(os.path.dirname(pid_file_path)):
    os.makedirs(os.path.dirname(pid_file_path))
with open(pid_file_path, "w+") as f:
    f.write(str(os.getpgrp()) + "\n")


def server_processes() -> List[List[str]]:
    main_cmds = [
        [
            "./manage.py",
            "rundjangoserver",
            *manage_args,
            *runserver_args,
            f"127.0.0.1:{django_port}",
        ],
        [
            "env",
            "PYTHONUNBUFFERED=1",
            "python3",
            *tornado_autoreload,
            "./manage.py",
            "runtornado",
            *manage_args,
            f"127.0.0.1:{tornado_port}",
        ],
    ]

    if options.streamlined:
        # The streamlined operation allows us to do many
        # things, but search/etc. features won't work.
        return main_cmds

    other_cmds = [
        ["./manage.py", "process_queue", "--all", *manage_args],
        [
            "env",
            "PGHOST=127.0.0.1",  # Force password authentication using .pgpass
            "./puppet/zulip/files/postgresql/process_fts_updates",
            "--quiet",
        ],
        ["./manage.py", "deliver_scheduled_messages"],
    ]

    # NORMAL (but slower) operation:
    return main_cmds + other_cmds


def do_one_time_webpack_compile() -> None:
    # We just need to compile webpack assets once at startup, not run a daemon,
    # in test mode.  Additionally, webpack-dev-server doesn't support running 2
    # copies on the same system, so this model lets us run the Puppeteer tests
    # with a running development server.
    subprocess.check_call(["./tools/webpack", "--quiet", "--test"])


def start_webpack_watcher() -> "subprocess.Popen[bytes]":
    webpack_cmd = ["./tools/webpack", "--watch", f"--port={webpack_port}"]
    if options.minify:
        webpack_cmd.append("--minify")
    if options.interface is None:
        # If interface is None and we're listening on all ports, we also need
        # to disable the webpack host check so that webpack will serve assets.
        webpack_cmd.append("--disable-host-check")
    if options.interface:
        webpack_cmd.append(f"--host={options.interface}")
    else:
        webpack_cmd.append("--host=0.0.0.0")
    return subprocess.Popen(webpack_cmd)


def transform_url(protocol: str, path: str, query: str, target_port: int, target_host: str) -> str:
    # generate url with target host
    host = ":".join((target_host, str(target_port)))
    # Here we are going to rewrite the path a bit so that it is in parity with
    # what we will have for production
    newpath = urlunparse((protocol, host, path, "", query, ""))
    return newpath


client: httpclient.AsyncHTTPClient


class BaseHandler(web.RequestHandler):
    # target server ip
    target_host: str = "127.0.0.1"
    # target server port
    target_port: int

    def _add_request_headers(
        self,
        exclude_lower_headers_list: Sequence[str] = [],
    ) -> httputil.HTTPHeaders:
        headers = httputil.HTTPHeaders()
        for header, v in self.request.headers.get_all():
            if header.lower() not in exclude_lower_headers_list:
                headers.add(header, v)
        return headers

    def get(self) -> None:
        pass

    def head(self) -> None:
        pass

    def post(self) -> None:
        pass

    def put(self) -> None:
        pass

    def patch(self) -> None:
        pass

    def options(self) -> None:
        pass

    def delete(self) -> None:
        pass

    async def prepare(self) -> None:
        assert self.request.method is not None
        assert self.request.remote_ip is not None
        if "X-REAL-IP" not in self.request.headers:
            self.request.headers["X-REAL-IP"] = self.request.remote_ip
        if "X-FORWARDED_PORT" not in self.request.headers:
            self.request.headers["X-FORWARDED-PORT"] = str(proxy_port)
        url = transform_url(
            self.request.protocol,
            self.request.path,
            self.request.query,
            self.target_port,
            self.target_host,
        )
        try:
            request = httpclient.HTTPRequest(
                url=url,
                method=self.request.method,
                headers=self._add_request_headers(["upgrade-insecure-requests"]),
                follow_redirects=False,
                body=getattr(self.request, "body"),
                allow_nonstandard_methods=True,
                # use large timeouts to handle polling requests
                connect_timeout=240.0,
                request_timeout=240.0,
                # https://github.com/tornadoweb/tornado/issues/2743
                decompress_response=False,
            )
            response = await client.fetch(request, raise_error=False)

            self.set_status(response.code, response.reason)
            self._headers = httputil.HTTPHeaders()  # clear tornado default header

            for header, v in response.headers.get_all():
                # some header appear multiple times, eg 'Set-Cookie'
                if header.lower() != "transfer-encoding":
                    self.add_header(header, v)
            if response.body:
                self.write(response.body)
            self.finish()
        except (ConnectionError, httpclient.HTTPError) as e:
            self.set_status(500)
            self.write("Internal server error:\n" + str(e))
            self.finish()


class WebPackHandler(BaseHandler):
    target_port = webpack_port


class DjangoHandler(BaseHandler):
    target_port = django_port


class TornadoHandler(BaseHandler):
    target_port = tornado_port


class Application(web.Application):
    def __init__(self, enable_logging: bool = False) -> None:
        super().__init__(
            [
                (r"/json/events.*", TornadoHandler),
                (r"/api/v1/events.*", TornadoHandler),
                (r"/webpack.*", WebPackHandler),
                (r"/.*", DjangoHandler),
            ],
            enable_logging=enable_logging,
        )

    def log_request(self, handler: web.RequestHandler) -> None:
        if self.settings["enable_logging"]:
            super().log_request(handler)


def print_listeners() -> None:
    # Since we can't import settings from here, we duplicate some
    # EXTERNAL_HOST logic from dev_settings.py.
    IS_DEV_DROPLET = pwd.getpwuid(os.getuid()).pw_name == "zulipdev"
    if IS_DEV_DROPLET:
        # Technically, the `zulip.` is a subdomain of the server, so
        # this is kinda misleading, but 99% of development is done on
        # the default/zulip subdomain.
        default_hostname = "zulip." + os.uname()[1].lower()
    else:
        default_hostname = "localhost"
    external_host = os.getenv("EXTERNAL_HOST", f"{default_hostname}:{proxy_port}")
    print(f"\nStarting Zulip on:\n\n\t{CYAN}http://{external_host}/{ENDC}\n\nInternal ports:")
    ports = [
        (proxy_port, "Development server proxy (connect here)"),
        (django_port, "Django"),
        (tornado_port, "Tornado"),
    ]

    if not options.test:
        ports.append((webpack_port, "webpack"))

    for port, label in ports:
        print(f"   {port}: {label}")
    print()


children = []


async def serve() -> None:
    global client

    AsyncIOMainLoop().install()

    if options.test:
        do_one_time_webpack_compile()
    else:
        children.append(start_webpack_watcher())

    for cmd in server_processes():
        children.append(subprocess.Popen(cmd))

    client = httpclient.AsyncHTTPClient()
    app = Application(enable_logging=options.enable_tornado_logging)
    try:
        app.listen(proxy_port, address=options.interface)
    except OSError as e:
        if e.errno == 98:
            print("\n\nERROR: You probably have another server running!!!\n\n")
        raise

    print_listeners()


loop = asyncio.new_event_loop()

try:
    loop.run_until_complete(serve())
    for s in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(s, loop.stop)
    loop.run_forever()
finally:
    for child in children:
        child.terminate()

    print("Waiting for children to stop...")
    for child in children:
        child.wait()

    # Remove pid file when development server closed correctly.
    os.remove(pid_file_path)
