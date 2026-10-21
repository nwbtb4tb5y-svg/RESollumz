import json
import re
from urllib.parse import urlparse
import urllib.error
import urllib.request


API_URL = "https://api.github.com/repos/Sollumz/Sollumz/releases?per_page=100"
USER_AGENT = "RESollumz-Loader"
REQUEST_TIMEOUT_SECONDS = 20
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_TAG_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class ReleaseError(RuntimeError):
    pass


def validate_tag(tag: str) -> str:
    if not _TAG_PATTERN.fullmatch(tag):
        raise ReleaseError(f"Invalid Sollumz release tag: {tag!r}")
    return tag


def parse_releases(payload: bytes) -> list[dict]:
    try:
        releases = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseError("GitHub returned invalid release metadata.") from exc
    if not isinstance(releases, list):
        raise ReleaseError("GitHub returned an unexpected release catalog.")

    result = []
    for release in releases:
        if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            continue
        validate_tag(tag)
        assets = release.get("assets")
        if not isinstance(assets, list):
            assets = []
        asset = next(
            (
                item for item in assets
                if isinstance(item, dict) and item.get("name") == "Sollumz.zip"
                and isinstance(item.get("browser_download_url"), str)
            ),
            None,
        )
        source_url = release.get("zipball_url")
        download_url = asset["browser_download_url"] if asset else source_url
        if not isinstance(download_url, str) or not download_url.startswith("https://"):
            continue
        digest = asset.get("digest") if asset else None
        if digest is not None and not re.fullmatch(r"sha256:[0-9a-fA-F]{64}", digest):
            digest = None
        result.append({
            "tag": tag,
            "name": str(release.get("name") or tag),
            "published_at": str(release.get("published_at") or ""),
            "download_url": download_url,
            "asset_name": asset["name"] if asset else "Source code (zip)",
            "sha256": digest[7:].lower() if digest else None,
        })
    return result


def fetch_releases(token: str = "") -> list[dict]:
    result = []
    page = 1
    while page <= 20:
        request = urllib.request.Request(
            f"{API_URL}&page={page}",
            headers=_headers(token, json_response=True),
        )
        try:
            with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            if exc.code == 403 and exc.headers.get("X-RateLimit-Remaining") == "0":
                raise ReleaseError("GitHub API rate limit reached. Add an optional token or try again later.") from exc
            raise ReleaseError(f"GitHub API request failed with HTTP {exc.code}.") from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ReleaseError(f"Could not contact GitHub: {exc}") from exc
        if len(payload) > MAX_RESPONSE_BYTES:
            raise ReleaseError("GitHub release catalog exceeded the allowed size.")
        page_releases = parse_releases(payload)
        if not page_releases:
            return result
        result.extend(page_releases)
        page += 1
    raise ReleaseError("GitHub release list exceeded the pagination limit.")


def download_release(release: dict, token: str = "") -> bytes:
    url = release.get("download_url")
    if not isinstance(url, str) or not _is_official_download_url(url):
        raise ReleaseError("Release download URL is not an approved GitHub HTTPS URL.")
    request = urllib.request.Request(url, headers=_headers(token))
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            if not _is_github_download_host(urlparse(response.geturl()).hostname):
                raise ReleaseError("GitHub redirected the release download to an untrusted host.")
            data = response.read(100 * 1024 * 1024 + 1)
    except urllib.error.HTTPError as exc:
        raise ReleaseError(f"Release download failed with HTTP {exc.code}.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ReleaseError(f"Could not download the Sollumz release: {exc}") from exc
    if len(data) > 100 * 1024 * 1024:
        raise ReleaseError("Sollumz release archive exceeded the 100 MiB limit.")
    return data


def _is_official_download_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        return False
    if parsed.hostname == "github.com":
        return parsed.path.startswith("/Sollumz/Sollumz/releases/download/")
    if parsed.hostname == "api.github.com":
        return parsed.path.startswith("/repos/Sollumz/Sollumz/zipball/")
    return False


def _is_github_download_host(host: str | None) -> bool:
    return host in {
        "github.com",
        "api.github.com",
        "codeload.github.com",
        "release-assets.githubusercontent.com",
        "objects.githubusercontent.com",
    }


def _headers(token: str = "", json_response: bool = False) -> dict[str, str]:
    headers = {"User-Agent": USER_AGENT}
    if json_response:
        headers["Accept"] = "application/vnd.github+json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers
