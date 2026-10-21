import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from resollumz_loader.core import github, manager, runtime


def make_release_archive(
    tag: str,
    package_folder: str = "Sollumz",
    include_dependencies: bool = True,
) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as output:
        root = f"{package_folder}/" if package_folder else ""
        initializer = "def register():\n    return True\n\ndef unregister():\n    return True\n"
        if include_dependencies:
            initializer = "from . import dependencies\n\n" + initializer
        output.writestr(root + "__init__.py", initializer)
        output.writestr(root + "auto_load.py", "pass\n")
        output.writestr(root + "known_paths.py", "def data_directory_path():\n    return 'shared'\n")
        if include_dependencies:
            output.writestr(
                root + "dependencies.py",
                "def data_directory_path():\n    return 'shared'\n"
                "def site_packages_path():\n    return 'shared'\n"
                "def requirements_path():\n    return 'shared'\n",
            )
        output.writestr(root + "release_marker.txt", tag)
    return archive.getvalue()


class ReleaseCatalogTests(unittest.TestCase):
    def test_headers_send_optional_token_as_bearer(self):
        token = "ghp_test_token"
        headers = github._headers(token, json_response=True)

        self.assertEqual(headers["Authorization"], f"Bearer {token}")
        self.assertEqual(headers["Accept"], "application/vnd.github+json")

    def test_parse_release_asset_digest_and_source_fallback(self):
        payload = json.dumps([
            {
                "tag_name": "v2.9.0",
                "name": "Sollumz 2.9.0",
                "published_at": "2026-01-01T00:00:00Z",
                "draft": False,
                "prerelease": False,
                "assets": [{
                    "name": "Sollumz.zip",
                    "browser_download_url": "https://github.com/Sollumz/Sollumz/releases/download/v2.9.0/Sollumz.zip",
                    "digest": "sha256:" + "a" * 64,
                }],
                "zipball_url": "https://api.github.com/repos/Sollumz/Sollumz/zipball/v2.9.0",
            },
            {
                "tag_name": "v2.4.2",
                "draft": False,
                "prerelease": False,
                "assets": [],
                "zipball_url": "https://api.github.com/repos/Sollumz/Sollumz/zipball/v2.4.2",
            },
            {"tag_name": "v9.0.0-beta", "draft": False, "prerelease": True},
        ]).encode()

        releases = github.parse_releases(payload)

        self.assertEqual([item["tag"] for item in releases], ["v2.9.0", "v2.4.2"])
        self.assertEqual(releases[0]["sha256"], "a" * 64)
        self.assertEqual(releases[1]["asset_name"], "Source code (zip)")
        self.assertIsNone(releases[1]["sha256"])

    def test_download_urls_are_limited_to_official_repository(self):
        self.assertTrue(github._is_official_download_url(
            "https://github.com/Sollumz/Sollumz/releases/download/v2.9.0/Sollumz.zip"
        ))
        self.assertTrue(github._is_official_download_url(
            "https://api.github.com/repos/Sollumz/Sollumz/zipball/v2.9.0"
        ))
        self.assertFalse(github._is_official_download_url("https://attacker.example/Sollumz.zip"))
        self.assertFalse(github._is_official_download_url(
            "https://github.com/attacker/Sollumz/releases/download/v2.9.0/Sollumz.zip"
        ))

    def test_download_release_accepts_optional_token(self):
        release = {"download_url": "https://github.com/Sollumz/Sollumz/releases/download/v2.9.0/Sollumz.zip"}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self, size):
                return b"archive-bytes"

            def geturl(self):
                return release["download_url"]

        def fake_urlopen(request, timeout):
            auth = request.headers.get("Authorization", "")
            self.assertTrue(auth.startswith("Bearer "))
            self.assertIn("ghp_test_token", auth)
            self.assertEqual(timeout, 60)
            return FakeResponse()

        with mock.patch("resollumz_loader.core.github.urllib.request.urlopen", side_effect=fake_urlopen):
            self.assertEqual(github.download_release(release, "ghp_test_token"), b"archive-bytes")

    def test_remove_addon_preferences_entry_removes_stale_managed_addon(self):
        class FakeAddons(list):
            def get(self, key):
                for item in self:
                    if getattr(item, "module", None) == key:
                        return item
                return None

            def new(self):
                entry = types.SimpleNamespace(module="")
                self.append(entry)
                return entry

        addons = FakeAddons([
            types.SimpleNamespace(module="resollumz_loader"),
            types.SimpleNamespace(module=manager.module_name("v2.7.2")),
        ])
        fake_bpy = types.SimpleNamespace(
            context=types.SimpleNamespace(
                preferences=types.SimpleNamespace(addons=addons)
            )
        )

        with mock.patch.dict(sys.modules, {"bpy": fake_bpy}):
            runtime.remove_addon_preferences_entry(manager.module_name("v2.7.2"))

        self.assertEqual([getattr(item, "module", None) for item in addons], ["resollumz_loader"])


class ArchiveInstallationTests(unittest.TestCase):
    def test_versions_sort_by_semver(self):
        self.assertEqual(
            manager.sort_versions(["legacy", "v2.9.0", "v2.10.0"]),
            ["v2.10.0", "v2.9.0", "legacy"],
        )

    def test_installs_and_loads_three_release_layouts(self):
        layouts = (
            ("v2.7.2", "Sollumz-2.7.2", False),
            ("v2.8.0", "Sollumz", True),
            ("v2.9.0", "Sollumz-2.9.0", True),
        )
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "versions"
            namespaces = []
            for tag, package_folder, include_dependencies in layouts:
                archive = make_release_archive(tag, package_folder, include_dependencies)
                digest = hashlib.sha256(archive).hexdigest()
                package_path = manager.install_archive(root, tag, archive, digest)
                self.assertEqual((package_path / "dependencies.py").is_file(), include_dependencies)
                self.assertTrue((package_path / "auto_load.py").is_file())
                self.assertEqual((package_path / "release_marker.txt").read_text(), tag)

                namespace = manager.module_name(tag)
                module = runtime._load_package(namespace, package_path, root / tag / "data")
                namespaces.append(namespace)
                self.assertTrue(module.register())
                if include_dependencies:
                    data_path = root / tag / "data"
                    self.assertEqual(module.dependencies.data_directory_path(), str(data_path))
                    self.assertEqual(
                        module.dependencies.site_packages_path(),
                        data_path / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages",
                    )
                    self.assertEqual(module.dependencies.requirements_path(), data_path / "requirements.txt")
                module.unregister()
                runtime._remove_package_modules(namespace)
                sys.path.remove(str(package_path.parent))

            self.assertEqual(manager.installed_versions(root), ["v2.9.0", "v2.8.0", "v2.7.2"])
            self.assertFalse(any(name == prefix or name.startswith(prefix + ".")
                                 for prefix in namespaces for name in __import__("sys").modules))

    def test_rejects_bad_hash_and_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "versions"
            archive = make_release_archive("v2.9.0")
            with self.assertRaises(github.ReleaseError):
                manager.install_archive(root, "v2.9.0", archive, "0" * 64)
            self.assertFalse(root.exists())

            malicious = io.BytesIO()
            with zipfile.ZipFile(malicious, "w") as output:
                output.writestr("../outside.txt", "no")
            with self.assertRaises(github.ReleaseError):
                manager.install_archive(root, "v1.0.0", malicious.getvalue(), None)
            self.assertEqual(manager.installed_versions(root), [])

    def test_remove_only_managed_release(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "versions"
            package = manager.install_archive(root, "v2.9.0", make_release_archive("v2.9.0"), None)
            self.assertTrue(package.is_dir())
            manager.remove_release(root, "v2.9.0")
            self.assertEqual(manager.installed_versions(root), [])


if __name__ == "__main__":
    unittest.main()
