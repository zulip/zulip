"""Upstream release providers for tools/update-dependency-versions.

A provider looks up the latest version of a package and the sha256(s)
of its release artifacts.  Every provider returns a `LatestRelease`
with the same shape regardless of upstream's plumbing; `cli.py` merges
the result back into `dependencies.json` without caring which provider
produced it.

Provider selection is driven by the `_updater.provider` key in each
dependencies.json entry.  See `puppet/zulip/files/dependencies.json`
for concrete examples of each provider's configuration.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from typing import Any

import requests

GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class LatestRelease:
    version: str
    # For arch-split binaries: {"amd64": "<hex>", "aarch64": "<hex>"}.
    # For source tarballs: a single hex string.
    sha256: dict[str, str] | str


class ProviderError(Exception):
    """Raised when an upstream fetch fails in a way the CLI should surface."""


def github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(session: requests.Session, url: str, **kwargs: Any) -> Any:
    r = session.get(url, timeout=30, **kwargs)
    r.raise_for_status()
    return r.json()


def _get_text(session: requests.Session, url: str) -> str:
    r = session.get(url, timeout=30)
    r.raise_for_status()
    return r.text


def _get_bytes(session: requests.Session, url: str) -> bytes:
    r = session.get(url, timeout=120)
    r.raise_for_status()
    return r.content


def _parse_first_hex(text: str) -> str:
    """Extract the first sha256-looking hex token from a sidecar checksum file."""
    m = re.search(r"\b([0-9a-fA-F]{64})\b", text)
    if not m:
        raise ProviderError(f"no sha256 hex token in checksum body: {text!r}")
    return m.group(1).lower()


def _parse_checksum_listing(text: str, filename: str) -> str:
    """Find the sha256 for `filename` in a `<hash>  <name>` style listing.

    Matches on the basename so that both "foo.tar.gz" and "./sub/foo.tar.gz"
    resolve to the same entry.
    """
    for line in text.splitlines():
        parts = line.strip().split()
        if (
            len(parts) >= 2
            and os.path.basename(parts[-1]) == filename
            and re.fullmatch(r"[0-9a-fA-F]{64}", parts[0])
        ):
            return parts[0].lower()
    raise ProviderError(f"filename {filename!r} not found in checksum listing")


def _render(template: str, params: dict[str, Any]) -> str:
    try:
        return template.format(**params)
    except KeyError as e:
        raise ProviderError(
            f"template {template!r} wants key {e.args[0]!r} that isn't in {sorted(params)}"
        ) from e


def github_release(session: requests.Session, name: str, entry: dict[str, Any]) -> LatestRelease:
    u = entry["_updater"]
    repo = u["repo"]
    release = _github_pick_release(
        session,
        repo,
        tag_pattern=u.get("tag_pattern"),
        allow_prereleases=u.get("allow_prereleases", False),
    )
    tag = release["tag_name"]
    prefix = u.get("tag_strip_prefix", "")
    version = tag.removeprefix(prefix) if prefix else tag

    # Build the per-asset URL templates and collect sha256 per arch.
    extras = {k: v for k, v in entry.items() if k not in ("version", "sha256", "_updater")}
    arch_map = u["arch_map"]
    checksum_cfg = u["checksum"]
    sha256_by_arch: dict[str, str] = {}

    # Pre-fetch a release_file checksum listing if that's the mechanism.
    listing: str | None = None
    if checksum_cfg["kind"] == "release_file":
        listing_name = _render(checksum_cfg["name"], {"version": version})
        asset_url = _find_release_asset_url(release, listing_name)
        listing = _get_text(session, asset_url)

    for arch, url_arch in arch_map.items():
        params = {**extras, "version": version, "arch": url_arch}
        asset_url = _render(u["asset_url"], params)
        kind = checksum_cfg["kind"]
        if kind == "sidecar":
            sidecar = asset_url + checksum_cfg["suffix"]
            sha = _parse_first_hex(_get_text(session, sidecar))
        elif kind == "release_file":
            assert listing is not None
            sha = _parse_checksum_listing(listing, asset_url.rsplit("/", 1)[-1])
        elif kind == "compute":
            # Falls back to downloading the whole asset and hashing it --
            # used only for grok_exporter, which publishes no checksums.
            sha = hashlib.sha256(_get_bytes(session, asset_url)).hexdigest()
        else:
            raise ProviderError(f"unknown checksum kind: {kind!r}")
        sha256_by_arch[arch] = sha

    return LatestRelease(version=version, sha256=sha256_by_arch)


def _github_pick_release(
    session: requests.Session,
    repo: str,
    *,
    tag_pattern: str | None,
    allow_prereleases: bool,
) -> dict[str, Any]:
    """Return the release to treat as the latest for this entry.

    With no options, uses the GitHub-provided /releases/latest (which
    hides prereleases but can still return non-semver tags the project
    has marked as latest).  If `tag_pattern` or `allow_prereleases` is
    set, paginates /releases and returns the first (newest) release
    matching the constraints -- used for projects like vector (ships
    dev tags alongside real versions) or grok_exporter (only publishes
    release-candidates marked as prereleases).
    """
    headers = github_headers()
    if tag_pattern is None and not allow_prereleases:
        return _get_json(session, f"{GITHUB_API}/repos/{repo}/releases/latest", headers=headers)
    pattern = re.compile(tag_pattern) if tag_pattern is not None else None
    page = 1
    while page <= 10:
        releases = _get_json(
            session,
            f"{GITHUB_API}/repos/{repo}/releases",
            headers=headers,
            params={"per_page": 30, "page": page},
        )
        if not releases:
            break
        for release in releases:
            if release.get("draft"):
                continue
            if not allow_prereleases and release.get("prerelease"):
                continue
            if pattern is not None and not pattern.fullmatch(release["tag_name"]):
                continue
            return release
        page += 1
    raise ProviderError(f"no release in {repo!r} matched the configured release filter")


def _find_release_asset_url(release: dict[str, Any], filename: str) -> str:
    for asset in release.get("assets", []):
        if asset["name"] == filename:
            return asset["browser_download_url"]
    raise ProviderError(f"asset {filename!r} not present in release {release.get('tag_name')!r}")


def github_commit(session: requests.Session, name: str, entry: dict[str, Any]) -> LatestRelease:
    u = entry["_updater"]
    repo = u["repo"]
    branch = u["branch"]
    commit = _get_json(
        session,
        f"{GITHUB_API}/repos/{repo}/commits/{branch}",
        headers=github_headers(),
    )
    sha_commit = commit["sha"]
    existing_sha256 = entry.get("sha256")
    # If the branch hasn't moved, avoid re-downloading the tarball just to
    # rehash bytes we've already verified.  GitHub's on-the-fly archive
    # tarballs are stable for a given commit.
    if sha_commit == entry.get("version") and isinstance(existing_sha256, str):
        return LatestRelease(version=sha_commit, sha256=existing_sha256)
    archive_url = _render(u["archive_url"], {"version": sha_commit})
    sha256 = hashlib.sha256(_get_bytes(session, archive_url)).hexdigest()
    return LatestRelease(version=sha_commit, sha256=sha256)


def golang(session: requests.Session, name: str, entry: dict[str, Any]) -> LatestRelease:
    u = entry["_updater"]
    arch_map = u["arch_map"]
    data = _get_json(session, "https://go.dev/dl/?mode=json")
    if not data:
        raise ProviderError("go.dev/dl returned no versions")
    latest = data[0]
    version = latest["version"].removeprefix("go")
    sha256_by_arch: dict[str, str] = {}
    files = latest.get("files", [])
    for arch, url_arch in arch_map.items():
        filename = f"go{version}.linux-{url_arch}.tar.gz"
        for f in files:
            if f.get("filename") == filename:
                sha256_by_arch[arch] = f["sha256"]
                break
        else:
            raise ProviderError(f"no file {filename!r} in go.dev feed")
    return LatestRelease(version=version, sha256=sha256_by_arch)


def sentry_cli(session: requests.Session, name: str, entry: dict[str, Any]) -> LatestRelease:
    u = entry["_updater"]
    app = u["app"]
    data = _get_json(session, f"https://release-registry.services.sentry.io/apps/{app}/latest")
    version = data["version"]
    sha256_by_arch: dict[str, str] = {}
    for arch, url_arch in u["arch_map"].items():
        asset_name = _render(u["asset_name_template"], {"arch": url_arch})
        file_info = data.get("files", {}).get(asset_name)
        if not file_info:
            raise ProviderError(f"asset {asset_name!r} missing from sentry registry")
        sha256_by_arch[arch] = file_info["checksums"]["sha256-hex"]
    return LatestRelease(version=version, sha256=sha256_by_arch)


def grafana(session: requests.Session, name: str, entry: dict[str, Any]) -> LatestRelease:
    u = entry["_updater"]
    data = _get_json(session, "https://grafana.com/api/grafana/versions")
    version: str | None = None
    for item in data.get("items", []):
        if item.get("channels", {}).get("stable"):
            version = item["version"]
            break
    if version is None:
        raise ProviderError("no stable grafana version in feed")
    sha256_by_arch: dict[str, str] = {}
    checksum_cfg = u["checksum"]
    for arch, url_arch in u["arch_map"].items():
        asset_url = _render(u["asset_url"], {"version": version, "arch": url_arch})
        if checksum_cfg["kind"] == "sidecar":
            sidecar = asset_url + checksum_cfg["suffix"]
            sha256_by_arch[arch] = _parse_first_hex(_get_text(session, sidecar))
        else:
            raise ProviderError(
                f"grafana provider supports checksum kind 'sidecar', got {checksum_cfg['kind']!r}"
            )
    return LatestRelease(version=version, sha256=sha256_by_arch)


PROVIDERS = {
    "github_release": github_release,
    "github_commit": github_commit,
    "golang": golang,
    "sentry_cli": sentry_cli,
    "grafana": grafana,
}


def fetch_latest(session: requests.Session, name: str, entry: dict[str, Any]) -> LatestRelease:
    provider = entry.get("_updater", {}).get("provider")
    if provider not in PROVIDERS:
        raise ProviderError(f"{name}: unknown provider {provider!r}")
    return PROVIDERS[provider](session, name, entry)
