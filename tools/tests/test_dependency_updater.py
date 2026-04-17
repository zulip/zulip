"""Tests for tools/update-dependency-versions."""

from __future__ import annotations

import hashlib
import io
import json
import re
import tempfile
from pathlib import Path
from unittest import TestCase, mock

import requests
import responses

from tools.lib.dependency_updater import cli, config, providers

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

AMD64_HEX = "a" * 64
AARCH64_HEX = "b" * 64
AMD64_HEX2 = "c" * 64
AARCH64_HEX2 = "d" * 64
SRC_HEX = "e" * 64


def github_release_entry() -> config.Entry:
    return {
        "version": "1.0.0",
        "sha256": {"amd64": AMD64_HEX, "aarch64": AARCH64_HEX},
        "_updater": {
            "provider": "github_release",
            "repo": "owner/repo",
            "tag_strip_prefix": "v",
            "arch_map": {"amd64": "amd64", "aarch64": "arm64"},
            "asset_url": "https://github.com/owner/repo/releases/download/v{version}/tool_linux_{arch}.tar.gz",
            "checksum": {"kind": "sidecar", "suffix": ".sha256"},
        },
    }


def github_release_release_file_entry() -> config.Entry:
    return {
        "version": "1.0.0",
        "sha256": {"amd64": AMD64_HEX, "aarch64": AARCH64_HEX},
        "_updater": {
            "provider": "github_release",
            "repo": "owner/repo",
            "tag_strip_prefix": "v",
            "arch_map": {"amd64": "amd64", "aarch64": "arm64"},
            "asset_url": "https://github.com/owner/repo/releases/download/v{version}/tool-{version}.linux-{arch}.tar.gz",
            "checksum": {"kind": "release_file", "name": "sha256sums.txt"},
        },
    }


def github_release_compute_entry() -> config.Entry:
    return {
        "version": "1.0.0",
        "sha256": {"amd64": AMD64_HEX},
        "_updater": {
            "provider": "github_release",
            "repo": "owner/repo",
            "tag_strip_prefix": "v",
            "arch_map": {"amd64": "amd64"},
            "asset_url": "https://github.com/owner/repo/releases/download/v{version}/tool-{version}-{arch}.zip",
            "checksum": {"kind": "compute"},
        },
    }


def github_commit_entry() -> config.Entry:
    return {
        "version": "deadbeef" * 5,
        "sha256": SRC_HEX,
        "_updater": {
            "provider": "github_commit",
            "repo": "owner/repo",
            "branch": "main",
            "archive_url": "https://github.com/owner/repo/archive/{version}.tar.gz",
        },
    }


# ---------------------------------------------------------------------------
# Provider tests
# ---------------------------------------------------------------------------


class GithubReleaseSidecarTest(TestCase):
    @responses.activate
    def test_fetch(self) -> None:
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(
            "https://github.com/owner/repo/releases/download/v2.1.0/tool_linux_amd64.tar.gz.sha256",
            body=f"{AMD64_HEX2}  tool_linux_amd64.tar.gz\n",
        )
        responses.get(
            "https://github.com/owner/repo/releases/download/v2.1.0/tool_linux_arm64.tar.gz.sha256",
            body=f"{AARCH64_HEX2}  tool_linux_arm64.tar.gz\n",
        )
        release = providers.fetch_latest(requests.Session(), "tool", github_release_entry())
        self.assertEqual(release.version, "2.1.0")
        self.assertEqual(release.sha256, {"amd64": AMD64_HEX2, "aarch64": AARCH64_HEX2})


class GithubReleaseFileTest(TestCase):
    @responses.activate
    def test_fetch(self) -> None:
        listing = (
            f"{AMD64_HEX2}  tool-2.1.0.linux-amd64.tar.gz\n"
            f"{AARCH64_HEX2}  tool-2.1.0.linux-arm64.tar.gz\n"
            f"ff  ignored_darwin.tar.gz\n"
        )
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={
                "tag_name": "v2.1.0",
                "assets": [
                    {
                        "name": "sha256sums.txt",
                        "browser_download_url": "https://example.test/sha256sums.txt",
                    }
                ],
            },
        )
        responses.get("https://example.test/sha256sums.txt", body=listing)
        release = providers.fetch_latest(
            requests.Session(), "tool", github_release_release_file_entry()
        )
        self.assertEqual(release.version, "2.1.0")
        self.assertEqual(release.sha256, {"amd64": AMD64_HEX2, "aarch64": AARCH64_HEX2})

    @responses.activate
    def test_missing_asset_in_listing(self) -> None:
        listing = f"{AMD64_HEX2}  tool-2.1.0.linux-amd64.tar.gz\n"
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={
                "tag_name": "v2.1.0",
                "assets": [
                    {
                        "name": "sha256sums.txt",
                        "browser_download_url": "https://example.test/sha256sums.txt",
                    }
                ],
            },
        )
        responses.get("https://example.test/sha256sums.txt", body=listing)
        with self.assertRaises(providers.ProviderError):
            providers.fetch_latest(requests.Session(), "tool", github_release_release_file_entry())

    @responses.activate
    def test_missing_listing_asset_in_release(self) -> None:
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        with self.assertRaises(providers.ProviderError):
            providers.fetch_latest(requests.Session(), "tool", github_release_release_file_entry())


class GithubReleaseComputeTest(TestCase):
    @responses.activate
    def test_fetch(self) -> None:
        body = b"the downloaded zip bytes"
        expected = hashlib.sha256(body).hexdigest()
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(
            "https://github.com/owner/repo/releases/download/v2.1.0/tool-2.1.0-amd64.zip",
            body=body,
        )
        release = providers.fetch_latest(requests.Session(), "tool", github_release_compute_entry())
        self.assertEqual(release.sha256, {"amd64": expected})


class GithubReleaseTagPatternTest(TestCase):
    """Entries can constrain which tag counts as a release (e.g. vector ships dev tags)."""

    @responses.activate
    def test_skips_nonmatching_tags(self) -> None:
        entry = github_release_entry()
        entry["_updater"]["tag_pattern"] = r"^v\d+\.\d+\.\d+$"
        responses.get(
            "https://api.github.com/repos/owner/repo/releases",
            json=[
                {"tag_name": "vdev-1", "prerelease": False, "assets": []},
                {"tag_name": "v2.1.0", "prerelease": False, "assets": []},
            ],
        )
        responses.get(
            re.compile(r".*/tool_linux_amd64\.tar\.gz\.sha256$"),
            body=f"{AMD64_HEX2}  x\n",
        )
        responses.get(
            re.compile(r".*/tool_linux_arm64\.tar\.gz\.sha256$"),
            body=f"{AARCH64_HEX2}  x\n",
        )
        release = providers.fetch_latest(requests.Session(), "tool", entry)
        self.assertEqual(release.version, "2.1.0")

    @responses.activate
    def test_skips_prereleases(self) -> None:
        entry = github_release_entry()
        entry["_updater"]["tag_pattern"] = r"^v\d+\.\d+\.\d+$"
        responses.get(
            "https://api.github.com/repos/owner/repo/releases",
            json=[
                {"tag_name": "v3.0.0", "prerelease": True, "assets": []},
                {"tag_name": "v2.1.0", "prerelease": False, "assets": []},
            ],
        )
        responses.get(re.compile(r".*\.sha256$"), body=f"{AMD64_HEX2}  x\n")
        release = providers.fetch_latest(requests.Session(), "tool", entry)
        self.assertEqual(release.version, "2.1.0")

    @responses.activate
    def test_no_match_raises(self) -> None:
        entry = github_release_entry()
        entry["_updater"]["tag_pattern"] = r"^v\d+\.\d+\.\d+$"
        responses.get(
            "https://api.github.com/repos/owner/repo/releases",
            json=[{"tag_name": "vdev-1", "prerelease": False, "assets": []}],
        )
        responses.get(
            "https://api.github.com/repos/owner/repo/releases",
            json=[],
        )
        with self.assertRaises(providers.ProviderError):
            providers.fetch_latest(requests.Session(), "tool", entry)

    @responses.activate
    def test_allow_prereleases(self) -> None:
        """grok_exporter case: every release is a prerelease, so /releases/latest 404s."""
        entry = github_release_entry()
        entry["_updater"]["allow_prereleases"] = True
        responses.get(
            "https://api.github.com/repos/owner/repo/releases",
            json=[
                {"tag_name": "v2.1.0", "prerelease": True, "assets": []},
                {"tag_name": "v2.0.0", "prerelease": True, "assets": []},
            ],
        )
        responses.get(re.compile(r".*\.sha256$"), body=f"{AMD64_HEX2}  x\n")
        release = providers.fetch_latest(requests.Session(), "tool", entry)
        self.assertEqual(release.version, "2.1.0")


class GithubReleaseExtraTemplateKeyTest(TestCase):
    """go-camo-style entry: extra consumer field (goversion) threaded into URL template."""

    @responses.activate
    def test_fetch(self) -> None:
        entry: config.Entry = {
            "version": "2.7.3",
            "goversion": "1260",
            "sha256": {"amd64": AMD64_HEX},
            "_updater": {
                "provider": "github_release",
                "repo": "cactus/go-camo",
                "tag_strip_prefix": "v",
                "arch_map": {"amd64": "amd64"},
                "asset_url": "https://github.com/cactus/go-camo/releases/download/v{version}/go-camo-{version}.go{goversion}.linux-{arch}.tar.gz",
                "checksum": {"kind": "release_file", "name": "SHA256"},
            },
        }
        listing = f"{AMD64_HEX2}  go-camo-2.7.3.go1260.linux-amd64.tar.gz\n"
        responses.get(
            "https://api.github.com/repos/cactus/go-camo/releases/latest",
            json={
                "tag_name": "v2.7.3",
                "assets": [
                    {
                        "name": "SHA256",
                        "browser_download_url": "https://example.test/SHA256",
                    }
                ],
            },
        )
        responses.get("https://example.test/SHA256", body=listing)
        release = providers.fetch_latest(requests.Session(), "go-camo", entry)
        self.assertEqual(release.sha256, {"amd64": AMD64_HEX2})


class GithubReleaseReservedConsumerFieldTest(TestCase):
    """A consumer field that collides with a template variable must not crash the render;
    the URL template's explicit {version}/{arch} values win over any such field."""

    @responses.activate
    def test_arch_field_is_overridden(self) -> None:
        entry: config.Entry = {
            "version": "1.0.0",
            "arch": "should-be-shadowed",
            "sha256": {"amd64": AMD64_HEX},
            "_updater": {
                "provider": "github_release",
                "repo": "owner/repo",
                "tag_strip_prefix": "v",
                "arch_map": {"amd64": "amd64"},
                "asset_url": "https://github.com/owner/repo/releases/download/v{version}/tool_linux_{arch}.tar.gz",
                "checksum": {"kind": "sidecar", "suffix": ".sha256"},
            },
        }
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(
            "https://github.com/owner/repo/releases/download/v2.1.0/tool_linux_amd64.tar.gz.sha256",
            body=f"{AMD64_HEX2}  x\n",
        )
        release = providers.fetch_latest(requests.Session(), "tool", entry)
        self.assertEqual(release.sha256, {"amd64": AMD64_HEX2})


class GithubCommitTest(TestCase):
    @responses.activate
    def test_fetch(self) -> None:
        new_sha = "f" * 40
        body = b"tarball bytes"
        expected_hash = hashlib.sha256(body).hexdigest()
        responses.get(
            "https://api.github.com/repos/owner/repo/commits/main",
            json={"sha": new_sha},
        )
        responses.get(
            f"https://github.com/owner/repo/archive/{new_sha}.tar.gz",
            body=body,
        )
        release = providers.fetch_latest(requests.Session(), "pkg", github_commit_entry())
        self.assertEqual(release.version, new_sha)
        self.assertEqual(release.sha256, expected_hash)

    @responses.activate
    def test_short_circuit_when_branch_unchanged(self) -> None:
        """Commit sha unchanged: return existing hash, don't re-download the tarball."""
        entry = github_commit_entry()
        pinned = entry["version"]
        pinned_sha = entry["sha256"]
        responses.get(
            "https://api.github.com/repos/owner/repo/commits/main",
            json={"sha": pinned},
        )
        # No archive URL registered: if the provider tries to fetch it,
        # the test fails with a connection-refused error.
        release = providers.fetch_latest(requests.Session(), "pkg", entry)
        self.assertEqual(release.version, pinned)
        self.assertEqual(release.sha256, pinned_sha)


class GolangTest(TestCase):
    @responses.activate
    def test_fetch(self) -> None:
        responses.get(
            "https://go.dev/dl/?mode=json",
            json=[
                {
                    "version": "go1.27.0",
                    "files": [
                        {
                            "filename": "go1.27.0.linux-amd64.tar.gz",
                            "os": "linux",
                            "arch": "amd64",
                            "sha256": AMD64_HEX2,
                        },
                        {
                            "filename": "go1.27.0.linux-arm64.tar.gz",
                            "os": "linux",
                            "arch": "arm64",
                            "sha256": AARCH64_HEX2,
                        },
                    ],
                }
            ],
        )
        entry: config.Entry = {
            "version": "1.26.0",
            "sha256": {"amd64": AMD64_HEX, "aarch64": AARCH64_HEX},
            "_updater": {
                "provider": "golang",
                "arch_map": {"amd64": "amd64", "aarch64": "arm64"},
            },
        }
        release = providers.fetch_latest(requests.Session(), "golang", entry)
        self.assertEqual(release.version, "1.27.0")
        self.assertEqual(release.sha256, {"amd64": AMD64_HEX2, "aarch64": AARCH64_HEX2})

    @responses.activate
    def test_missing_file(self) -> None:
        responses.get(
            "https://go.dev/dl/?mode=json",
            json=[{"version": "go1.27.0", "files": []}],
        )
        entry: config.Entry = {
            "_updater": {
                "provider": "golang",
                "arch_map": {"amd64": "amd64"},
            },
        }
        with self.assertRaises(providers.ProviderError):
            providers.fetch_latest(requests.Session(), "golang", entry)


class SentryCliTest(TestCase):
    @responses.activate
    def test_fetch(self) -> None:
        responses.get(
            "https://release-registry.services.sentry.io/apps/sentry-cli/latest",
            json={
                "version": "3.1.0",
                "files": {
                    "sentry-cli-Linux-x86_64": {
                        "checksums": {"sha256-hex": AMD64_HEX2},
                        "url": "https://ignored",
                    },
                    "sentry-cli-Linux-aarch64": {
                        "checksums": {"sha256-hex": AARCH64_HEX2},
                        "url": "https://ignored",
                    },
                },
            },
        )
        entry: config.Entry = {
            "version": "2.0.0",
            "sha256": {"amd64": AMD64_HEX, "aarch64": AARCH64_HEX},
            "_updater": {
                "provider": "sentry_cli",
                "app": "sentry-cli",
                "arch_map": {"amd64": "x86_64", "aarch64": "aarch64"},
                "asset_name_template": "sentry-cli-Linux-{arch}",
            },
        }
        release = providers.fetch_latest(requests.Session(), "sentry-cli", entry)
        self.assertEqual(release.version, "3.1.0")
        self.assertEqual(release.sha256, {"amd64": AMD64_HEX2, "aarch64": AARCH64_HEX2})


class GrafanaTest(TestCase):
    @responses.activate
    def test_picks_latest_stable(self) -> None:
        responses.get(
            "https://grafana.com/api/grafana/versions",
            json={
                "items": [
                    {"version": "13.1.0-nightly", "channels": {"stable": False, "nightly": True}},
                    {"version": "13.0.0", "channels": {"stable": True}},
                    {"version": "12.3.3", "channels": {"stable": True}},
                ]
            },
        )
        responses.get(
            "https://dl.grafana.com/oss/release/grafana-13.0.0.linux-amd64.tar.gz.sha256",
            body=AMD64_HEX2,
        )
        responses.get(
            "https://dl.grafana.com/oss/release/grafana-13.0.0.linux-arm64.tar.gz.sha256",
            body=AARCH64_HEX2,
        )
        entry: config.Entry = {
            "version": "12.3.3",
            "sha256": {"amd64": AMD64_HEX, "aarch64": AARCH64_HEX},
            "_updater": {
                "provider": "grafana",
                "arch_map": {"amd64": "amd64", "aarch64": "arm64"},
                "asset_url": "https://dl.grafana.com/oss/release/grafana-{version}.linux-{arch}.tar.gz",
                "checksum": {"kind": "sidecar", "suffix": ".sha256"},
            },
        }
        release = providers.fetch_latest(requests.Session(), "grafana", entry)
        self.assertEqual(release.version, "13.0.0")

    @responses.activate
    def test_no_stable(self) -> None:
        responses.get(
            "https://grafana.com/api/grafana/versions",
            json={"items": [{"version": "x", "channels": {"stable": False}}]},
        )
        entry: config.Entry = {
            "_updater": {
                "provider": "grafana",
                "arch_map": {"amd64": "amd64"},
                "asset_url": "https://dl.grafana.com/oss/release/g-{version}-{arch}.tar.gz",
                "checksum": {"kind": "sidecar", "suffix": ".sha256"},
            },
        }
        with self.assertRaises(providers.ProviderError):
            providers.fetch_latest(requests.Session(), "grafana", entry)


class UnknownProviderTest(TestCase):
    def test_raises(self) -> None:
        entry: config.Entry = {"_updater": {"provider": "nope"}}
        with self.assertRaises(providers.ProviderError):
            providers.fetch_latest(requests.Session(), "x", entry)


class HelperParsingTest(TestCase):
    def test_parse_first_hex_accepts_bare(self) -> None:
        self.assertEqual(providers._parse_first_hex(AMD64_HEX + "\n"), AMD64_HEX)

    def test_parse_first_hex_accepts_shasum_format(self) -> None:
        self.assertEqual(providers._parse_first_hex(f"{AMD64_HEX}  foo.tar.gz\n"), AMD64_HEX)

    def test_parse_first_hex_rejects_nonsense(self) -> None:
        with self.assertRaises(providers.ProviderError):
            providers._parse_first_hex("not a hash")

    def test_parse_checksum_listing_matches_by_basename(self) -> None:
        body = f"{AMD64_HEX}  ./subdir/foo.tar.gz\n{AARCH64_HEX}  bar.tar.gz\n"
        self.assertEqual(providers._parse_checksum_listing(body, "foo.tar.gz"), AMD64_HEX)
        self.assertEqual(providers._parse_checksum_listing(body, "bar.tar.gz"), AARCH64_HEX)

    def test_parse_checksum_listing_rejects_missing(self) -> None:
        with self.assertRaises(providers.ProviderError):
            providers._parse_checksum_listing(f"{AMD64_HEX}  foo.tar.gz\n", "bar.tar.gz")


class GithubHeadersTest(TestCase):
    def test_token_set(self) -> None:
        with mock.patch.dict("os.environ", {"GITHUB_TOKEN": "ghp_xxx"}):
            h = providers.github_headers()
        self.assertEqual(h["Authorization"], "Bearer ghp_xxx")

    def test_token_unset(self) -> None:
        env = dict(__import__("os").environ)
        env.pop("GITHUB_TOKEN", None)
        with mock.patch.dict("os.environ", env, clear=True):
            h = providers.github_headers()
        self.assertNotIn("Authorization", h)


# ---------------------------------------------------------------------------
# Config round-trip tests
# ---------------------------------------------------------------------------


class ConfigTest(TestCase):
    def test_shipped_file_round_trips(self) -> None:
        path = config.DEPS_PATH
        original = path.read_text()
        deps = config.load(path)
        self.assertEqual(config.serialize(deps), original)

    def test_dump_writes_trailing_newline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "out.json"
            config.dump({"a": {"version": "1"}}, p)
            self.assertTrue(p.read_text().endswith("\n"))


# ---------------------------------------------------------------------------
# CLI integration tests (a tmpdir-backed dependencies.json + mocked HTTP)
# ---------------------------------------------------------------------------


class CliTest(TestCase):
    def _write_deps(self, tmp: Path, deps: config.Deps) -> Path:
        p = tmp / "dependencies.json"
        config.dump(deps, p)
        return p

    @responses.activate
    def test_dry_run_prints_diff(self) -> None:
        # mock: release bumps from 1.0.0 -> 2.1.0
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(
            re.compile(r".*/releases/download/v2\.1\.0/tool_linux_amd64\.tar\.gz\.sha256$"),
            body=f"{AMD64_HEX2}  tool_linux_amd64.tar.gz\n",
        )
        responses.get(
            re.compile(r".*/releases/download/v2\.1\.0/tool_linux_arm64\.tar\.gz\.sha256$"),
            body=f"{AARCH64_HEX2}  tool_linux_arm64.tar.gz\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), {"tool": github_release_entry()})
            with mock.patch.object(config, "DEPS_PATH", path):
                stdout = io.StringIO()
                with mock.patch("sys.stdout", stdout):
                    rc = cli.main(["--dry-run"])
            self.assertEqual(rc, 0)
            self.assertIn("2.1.0", stdout.getvalue())
            # File untouched.
            self.assertIn('"version": "1.0.0"', path.read_text())

    @responses.activate
    def test_write_mode_updates_file(self) -> None:
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(
            re.compile(r".*/tool_linux_amd64\.tar\.gz\.sha256$"),
            body=f"{AMD64_HEX2}  x\n",
        )
        responses.get(
            re.compile(r".*/tool_linux_arm64\.tar\.gz\.sha256$"),
            body=f"{AARCH64_HEX2}  x\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), {"tool": github_release_entry()})
            with mock.patch.object(config, "DEPS_PATH", path):
                stdout = io.StringIO()
                with mock.patch("sys.stdout", stdout):
                    rc = cli.main([])
            self.assertEqual(rc, 0)
            result = json.loads(path.read_text())
            self.assertEqual(result["tool"]["version"], "2.1.0")
            self.assertEqual(
                result["tool"]["sha256"],
                {"amd64": AMD64_HEX2, "aarch64": AARCH64_HEX2},
            )
            # _updater preserved.
            self.assertIn("_updater", result["tool"])

    @responses.activate
    def test_check_mode_exits_1_when_stale(self) -> None:
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(
            re.compile(r".*\.sha256$"),
            body=f"{AMD64_HEX2}  x\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), {"tool": github_release_entry()})
            with mock.patch.object(config, "DEPS_PATH", path):
                rc = cli.main(["--check"])
            self.assertEqual(rc, 1)
            # File must not be written.
            self.assertIn('"version": "1.0.0"', path.read_text())

    @responses.activate
    def test_check_mode_exits_0_when_current(self) -> None:
        # Upstream still reports 1.0.0 with the same hashes.
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v1.0.0", "assets": []},
        )
        responses.get(
            re.compile(r".*/tool_linux_amd64\.tar\.gz\.sha256$"),
            body=f"{AMD64_HEX}  x\n",
        )
        responses.get(
            re.compile(r".*/tool_linux_arm64\.tar\.gz\.sha256$"),
            body=f"{AARCH64_HEX}  x\n",
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), {"tool": github_release_entry()})
            with mock.patch.object(config, "DEPS_PATH", path):
                rc = cli.main(["--check"])
            self.assertEqual(rc, 0)

    @responses.activate
    def test_package_filter_ignores_others(self) -> None:
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            json={"tag_name": "v2.1.0", "assets": []},
        )
        responses.get(re.compile(r".*\.sha256$"), body=f"{AMD64_HEX2}  x\n")
        # Two entries; we only ask to update one.  The untouched entry
        # keeps its original sha256 unchanged.
        entries: config.Deps = {
            "tool": github_release_entry(),
            "other": {
                "version": "1.2.3",
                "sha256": "untouched",
                "_updater": {"provider": "github_release"},  # never called
            },
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), entries)
            with mock.patch.object(config, "DEPS_PATH", path):
                stdout = io.StringIO()
                with mock.patch("sys.stdout", stdout):
                    rc = cli.main(["tool"])
            self.assertEqual(rc, 0)
            result = json.loads(path.read_text())
            self.assertEqual(result["tool"]["version"], "2.1.0")
            self.assertEqual(result["other"]["sha256"], "untouched")

    def test_unknown_package_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), {"tool": github_release_entry()})
            with mock.patch.object(config, "DEPS_PATH", path):
                rc = cli.main(["does-not-exist"])
            self.assertEqual(rc, 2)

    def test_workers_must_be_positive(self) -> None:
        with self.assertRaises(SystemExit):
            cli.main(["--workers=0"])
        with self.assertRaises(SystemExit):
            cli.main(["--workers=-3"])

    @responses.activate
    def test_provider_error_reported_rc1(self) -> None:
        responses.get(
            "https://api.github.com/repos/owner/repo/releases/latest",
            status=500,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write_deps(Path(tmp), {"tool": github_release_entry()})
            with (
                mock.patch.object(config, "DEPS_PATH", path),
                mock.patch("sys.stdout", io.StringIO()),
                mock.patch("sys.stderr", io.StringIO()) as stderr,
            ):
                rc = cli.main(["--dry-run"])
            self.assertEqual(rc, 1)
            self.assertIn("tool:", stderr.getvalue())

    def test_apply_preserves_extras_and_updater(self) -> None:
        entry: config.Entry = {
            "version": "1.0.0",
            "goversion": "1260",
            "sha256": {"amd64": AMD64_HEX},
            "_updater": {"provider": "github_release"},
        }
        release = providers.LatestRelease(version="2.0.0", sha256={"amd64": AMD64_HEX2})
        result = cli._apply(entry, release)
        self.assertEqual(result["version"], "2.0.0")
        self.assertEqual(result["sha256"], {"amd64": AMD64_HEX2})
        self.assertEqual(result["goversion"], "1260")
        # _updater should be at the end after round-trip.
        self.assertEqual(list(result.keys())[-1], "_updater")
