"""Manual, branch-pinned software updater for MyGPT.

Modeled on the confirmed branch-pinned updater of Cortex LLMHoster
(codero-sus/Cortex_LLMHoster), adapted for MyGPT: MyGPT runs straight from a
directory of source files rather than an installed package, so an update is a
*pinned archive sync* instead of a pip install.

How it works
------------
* **Check** — reads the head commit of the pinned branch
  (``codero-sus/MyGPT``, branch ``main`` by default; override with the
  ``MYGPT_UPDATE_REF`` environment variable) via the GitHub API, then reads
  ``mygpt/__init__.py`` at that exact commit to learn the newest version.
* **Install** — only after the user confirms the commit ID shown by a check:
  downloads the immutable archive ``https://github.com/codero-sus/MyGPT/
  archive/<sha>.zip``, verifies it looks like MyGPT, and syncs it over the
  app directory. Everything the user *learned* is preserved: ``data/``
  (memory, weights, facts, episodes, cortex settings), ``.git/``, ``.venv/``,
  dotfiles, and locally auto-written ``skills/handle_*.py`` files. A server
  restart finishes the update.

Nothing runs automatically: checks happen only when requested from the UI or
the API, and installation requires the confirmed commit ID.

MyGPT is distributed under the MyGPT Personal-Use License (see LICENSE):
free to download and run unmodified for personal, non-commercial use.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass

REPOSITORY = "codero-sus/MyGPT"
# Branch-pinned update source. Like Cortex LLMHoster, the updater tracks the
# exact branch it ships on; override with MYGPT_UPDATE_REF.
UPDATE_REF = os.environ.get("MYGPT_UPDATE_REF", "arena/01a0f6e2-mygpt")
GITHUB_API = f"https://api.github.com/repos/{REPOSITORY}"
_GITHUB_HEADERS = {
    "accept": "application/vnd.github+json",
    "user-agent": "MyGPT-Updater",
}
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}")
_VERSION_PATTERN = re.compile(r"\d+(?:\.\d+){1,3}")
_VERSION_LINE = re.compile(r"__version__\s*=\s*[\"']([^\"']+)[\"']")
CHECK_TIMEOUT = 12.0          # seconds for each GitHub API call
DOWNLOAD_TIMEOUT = 300.0      # seconds to fetch the release archive
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024

# Never touched by an update: learned state, VCS, virtualenv, caches, dotfiles.
PRESERVE_DIRS = {"data", ".git", ".venv", "__pycache__"}
# Directories replaced wholesale with the upstream copy.
REPLACE_DIRS = {"mygpt", "static", "templates"}
# Directories merged: archive files win, local extras (learned skills) survive.
MERGE_DIRS = {"skills"}


class UpdateError(RuntimeError):
    """A safe, user-displayable updater failure."""


@dataclass(frozen=True)
class UpdateInfo:
    current_version: str
    latest_version: str
    source_repository: str
    source_ref: str
    commit_sha: str
    update_available: bool

    def as_dict(self) -> dict:
        return {
            "current_version": self.current_version,
            "latest_version": self.latest_version,
            "source_repository": self.source_repository,
            "source_ref": self.source_ref,
            "commit_sha": self.commit_sha,
            "update_available": self.update_available,
        }


def _version_key(version: str) -> tuple:
    if not _VERSION_PATTERN.fullmatch(version):
        raise UpdateError("The update source contains an unsupported version format.")
    parts = tuple(int(p) for p in version.split("."))
    return (parts + (0, 0, 0, 0))[:4]


# --------------------------------------------------------------------- check
def _github_json(url: str, params: dict | None = None) -> dict:
    if params:
        url += "?" + "&".join(f"{k}={urllib.parse.quote(str(v), safe='')}"
                               for k, v in params.items())
    req = urllib.request.Request(url, headers=_GITHUB_HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=CHECK_TIMEOUT) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise UpdateError(
                "The configured update branch or project file was not found on GitHub.")
        if exc.code == 403 and exc.headers.get("x-ratelimit-remaining") == "0":
            raise UpdateError(
                "GitHub's unauthenticated update-check rate limit was reached. Try later.")
        raise UpdateError(f"GitHub returned HTTP {exc.code} while checking for updates.")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise UpdateError("Could not reach GitHub to check for updates.") from exc
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise UpdateError("GitHub returned an invalid update-check response.") from exc
    if not isinstance(payload, dict):
        raise UpdateError("GitHub returned an invalid update-check response.")
    return payload


def _quote_ref(ref: str) -> str:
    return urllib.parse.quote(ref, safe="")


def check_for_updates(current_version: str, ref: str | None = None) -> UpdateInfo:
    """Read the pinned branch head and its declared version from GitHub."""
    branch = ref or UPDATE_REF
    branch_data = _github_json(f"{GITHUB_API}/branches/{_quote_ref(branch)}")
    commit = branch_data.get("commit")
    commit_sha = commit.get("sha") if isinstance(commit, dict) else None
    if not isinstance(commit_sha, str) or not _COMMIT_PATTERN.fullmatch(commit_sha):
        raise UpdateError("GitHub returned an invalid update commit ID.")

    contents = _github_json(f"{GITHUB_API}/contents/mygpt/__init__.py",
                            params={"ref": commit_sha})
    encoded = contents.get("content")
    if not isinstance(encoded, str):
        raise UpdateError("The update source did not include version metadata.")
    try:
        init_src = base64.b64decode(encoded, validate=False).decode("utf-8")
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateError("The update source contains invalid version metadata.") from exc
    m = _VERSION_LINE.search(init_src)
    if not m:
        raise UpdateError("The update source does not declare a version.")
    latest_version = m.group(1)

    return UpdateInfo(
        current_version=current_version,
        latest_version=latest_version,
        source_repository=REPOSITORY,
        source_ref=branch,
        commit_sha=commit_sha,
        update_available=_version_key(latest_version) > _version_key(current_version),
    )


# ------------------------------------------------------------------- install
def _download_archive(commit_sha: str) -> bytes:
    url = f"https://github.com/{REPOSITORY}/archive/{commit_sha}.zip"
    req = urllib.request.Request(url, headers={"user-agent": "MyGPT-Updater"})
    try:
        with urllib.request.urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            chunks, buf = [], 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                buf += len(chunk)
                if buf > MAX_ARCHIVE_BYTES:
                    raise UpdateError("The update archive is unexpectedly large; aborted.")
                chunks.append(chunk)
    except urllib.error.HTTPError as exc:
        raise UpdateError(f"Could not download the update archive (HTTP {exc.code}).")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        raise UpdateError("Could not reach GitHub to download the update.") from exc
    return b"".join(chunks)


def _looks_like_mygpt(root: os.PathLike) -> bool:
    return (os.path.isfile(os.path.join(root, "app.py"))
            and os.path.isdir(os.path.join(root, "mygpt"))
            and os.path.isfile(os.path.join(root, "mygpt", "brain.py")))


def _sync_tree(src: str, dst: str) -> None:
    """Replace dst with src's contents (used for wholesale dirs)."""
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _merge_dir(src: str, dst: str) -> None:
    """Copy src files over dst; keep local files absent from src."""
    os.makedirs(dst, exist_ok=True)
    for name in os.listdir(src):
        s = os.path.join(src, name)
        d = os.path.join(dst, name)
        if os.path.isdir(s):
            _merge_dir(s, d)
        else:
            shutil.copy2(s, d)


def install_from_commit(commit_sha: str, app_dir: str,
                        ref: str | None = None) -> dict:
    """Sync the immutable archive of a confirmed commit over the app dir.

    Preserves learned state (``data/``), ``.git``, ``.venv``, dotfiles and
    auto-written skills. Returns a small summary dict.
    """
    if not _COMMIT_PATTERN.fullmatch(commit_sha or ""):
        raise UpdateError("Refusing to install an invalid update commit ID.")
    app_dir = os.path.abspath(app_dir)
    if not os.path.isdir(app_dir):
        raise UpdateError("The application directory does not exist.")

    blob = _download_archive(commit_sha)
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile as exc:
        raise UpdateError("The downloaded update archive is not a valid zip file.") from exc

    tmp = tempfile.mkdtemp(prefix="mygpt-update-")
    try:
        try:
            zf.extractall(tmp)
        except (OSError, zipfile.BadZipFile) as exc:
            raise UpdateError("Could not unpack the update archive.") from exc
        entries = os.listdir(tmp)
        if len(entries) != 1 or not os.path.isdir(os.path.join(tmp, entries[0])):
            raise UpdateError("The update archive has an unexpected layout.")
        src_root = os.path.join(tmp, entries[0])
        if not _looks_like_mygpt(src_root):
            raise UpdateError("The archive does not look like MyGPT; install aborted.")

        replaced, kept = [], sorted(PRESERVE_DIRS)
        for name in os.listdir(src_root):
            s = os.path.join(src_root, name)
            d = os.path.join(app_dir, name)
            if name in PRESERVE_DIRS or name.startswith("."):
                continue
            if name in REPLACE_DIRS and os.path.isdir(s):
                _sync_tree(s, d)
                replaced.append(name + "/")
            elif name in MERGE_DIRS and os.path.isdir(s):
                _merge_dir(s, d)
                replaced.append(name + "/ (merged, learned skills kept)")
            elif os.path.isdir(s):
                _sync_tree(s, d)
                replaced.append(name + "/")
            else:
                shutil.copy2(s, d)
                replaced.append(name)

        data_dir = os.path.join(app_dir, "data")
        os.makedirs(data_dir, exist_ok=True)
        marker = {
            "commit_sha": commit_sha, "ref": ref or UPDATE_REF,
            "installed_at": round(time.time()),
            "repository": REPOSITORY,
        }
        with open(os.path.join(data_dir, "last_update.json"), "w",
                  encoding="utf-8") as f:
            json.dump(marker, f, ensure_ascii=False)
        return {"replaced": replaced, "preserved": kept, **marker}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def last_update(data_dir: str) -> dict | None:
    path = os.path.join(data_dir, "last_update.json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


# ----------------------------------------------------------------------- CLI
def _app_dir() -> str:
    """The MyGPT root: the folder that contains the ``mygpt`` package."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main(argv: list[str] | None = None) -> int:
    """Command-line updater, used by ``updater.sh`` / ``updater.bat``.

    Usage:
        python -m mygpt.updater             check, then confirm to install
        python -m mygpt.updater --check     only check, never install
        python -m mygpt.updater --yes       install without asking
    """
    import argparse
    from . import __version__

    parser = argparse.ArgumentParser(
        prog="mygpt-updater",
        description="Manual, branch-pinned MyGPT update checker/installer.")
    parser.add_argument("--check", action="store_true",
                        help="only check for updates; never install")
    parser.add_argument("--yes", action="store_true",
                        help="install without asking (still pinned to the "
                             "checked commit)")
    args = parser.parse_args(argv)

    print(f"MyGPT updater — current version {__version__}")
    print(f"Update source: github.com/{REPOSITORY} (branch {UPDATE_REF})")
    try:
        info = check_for_updates(__version__)
    except UpdateError as exc:
        print(f"Update check failed: {exc}")
        return 1
    print(f"Branch head commit : {info.commit_sha}")
    print(f"Latest version     : {info.latest_version}")
    if not info.update_available:
        print(f"MyGPT {__version__} is up to date.")
        return 0

    print(f"\nUpdate available: {info.current_version} -> {info.latest_version}")
    if args.check:
        print("Check-only mode: nothing was installed.")
        return 0
    if not args.yes:
        try:
            answer = input(f"Install commit {info.commit_sha[:12]} now? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            print("Update cancelled. Your installation was not modified.")
            return 0

    print("Downloading and installing the pinned update "
          "(data/, .git, .venv and learned skills are preserved)…")
    try:
        summary = install_from_commit(info.commit_sha, _app_dir(),
                                      ref=info.source_ref)
    except UpdateError as exc:
        print(f"Update failed: {exc}")
        return 1
    print(f"Installed MyGPT {info.latest_version} (commit {info.commit_sha[:12]}).")
    print("Preserved: " + ", ".join(summary["preserved"]))
    print("Restart MyGPT (./run.sh or python app.py) to load the new version.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
