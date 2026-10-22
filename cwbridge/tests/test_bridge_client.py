import json
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cwbridge.client import (
    CWBridgeCancelled,
    CWBridgeError,
    convert_file,
    replace_file_with_backup,
    resource_format_for_path,
)
from cwbridge.ytd_index import IndexedTexture, choose_texture, index_ytd_directory
from cwbridge.xml_import import stage_xml_for_import


class BridgeClientTests(unittest.TestCase):
    def test_replaces_model_and_keeps_original_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "model.yft"
            replacement = root / "converted.yft"
            original.write_bytes(b"original")
            replacement.write_bytes(b"converted")

            backup = replace_file_with_backup(original, replacement)

            self.assertEqual(original.read_bytes(), b"converted")
            self.assertEqual(backup, (root / "model.yft.backup").resolve())
            self.assertEqual(backup.read_bytes(), b"original")

    def test_refuses_to_overwrite_an_existing_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "model.yft"
            replacement = root / "converted.yft"
            backup = root / "model.yft.backup"
            original.write_bytes(b"original")
            replacement.write_bytes(b"converted")
            backup.write_bytes(b"existing backup")

            with self.assertRaisesRegex(CWBridgeError, "Backup already exists"):
                replace_file_with_backup(original, replacement)

            self.assertEqual(original.read_bytes(), b"original")
            self.assertEqual(backup.read_bytes(), b"existing backup")

    def test_preserves_original_if_replacement_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "model.yft"
            replacement = root / "converted.yft"
            backup = root / "model.yft.backup"
            original.write_bytes(b"original")
            replacement.write_bytes(b"converted")

            with patch("cwbridge.client.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaisesRegex(CWBridgeError, "backup is available"):
                    replace_file_with_backup(original, replacement)

            self.assertEqual(original.read_bytes(), b"original")
            self.assertEqual(backup.read_bytes(), b"original")
            self.assertEqual(replacement.read_bytes(), b"converted")

    def test_recognizes_supported_binary_model_paths(self):
        self.assertEqual(resource_format_for_path(Path("model.yft")), "yft")
        self.assertEqual(resource_format_for_path(Path("MODEL.YDR")), "ydr")

    def test_rejects_unsupported_binary_model_paths(self):
        with self.assertRaisesRegex(CWBridgeError, "Supported formats"):
            resource_format_for_path(Path("model.yds"))

    def test_returns_success_response(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path = Path(temp) / "input.ytd"
            output_path = Path(temp) / "output.xml"
            input_path.touch()
            expected = {
                "ok": True,
                "outputPath": str(output_path.resolve()),
            }
            process_result = subprocess.CompletedProcess(["bridge"], 0, json.dumps(expected), "")
            with patch("cwbridge.client.find_bridge_command", return_value=["bridge"]), \
                    patch("cwbridge.client._run_bridge", return_value=process_result) as run:
                result = convert_file(input_path, output_path, operation="to_xml")

            self.assertEqual(result, expected)
            self.assertEqual(json.loads(run.call_args.args[1])["operation"], "to_xml")

    def test_reports_bridge_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path = Path(temp) / "input.ytd"
            output_path = Path(temp) / "output.xml"
            input_path.touch()
            process_result = subprocess.CompletedProcess(
                ["bridge"],
                1,
                json.dumps({
                    "ok": False,
                    "error": {"code": "conversion_failed", "message": "invalid resource"},
                }),
                "stack trace",
            )
            with patch("cwbridge.client.find_bridge_command", return_value=["bridge"]), \
                    patch("cwbridge.client._run_bridge", return_value=process_result):
                with self.assertRaisesRegex(CWBridgeError, "conversion_failed: invalid resource"):
                    convert_file(input_path, output_path, operation="to_xml")

    def test_cancels_running_bridge_process(self):
        with tempfile.TemporaryDirectory() as temp:
            input_path = Path(temp) / "input.ytd"
            output_path = Path(temp) / "output.xml"
            input_path.touch()
            cancel_event = threading.Event()
            timer = threading.Timer(0.2, cancel_event.set)
            timer.start()
            started = time.monotonic()

            with self.assertRaisesRegex(CWBridgeCancelled, "cancelled"):
                convert_file(
                    input_path,
                    output_path,
                    operation="to_xml",
                    bridge_command=[sys.executable, "-c", "import time; time.sleep(30)"],
                    timeout=10,
                    cancel_event=cancel_event,
                )

            timer.join()
            self.assertLess(time.monotonic() - started, 5)


class YtdIndexTests(unittest.TestCase):
    def test_indexes_ytd_and_reuses_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            cache = root / "cache"
            source.mkdir()
            ytd_path = source / "model.ytd"
            ytd_path.write_bytes(b"fixture")
            progress = []

            def convert(_input, output, **_kwargs):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    "<TextureDictionary><Item><FileName>diffuse.dds</FileName></Item></TextureDictionary>",
                    encoding="utf-8",
                )
                (output.parent / "diffuse.dds").write_bytes(b"DDS fixture")
                return {"ok": True, "outputPath": str(output)}

            with patch("cwbridge.ytd_index.find_bridge_command", return_value=["bridge"]), \
                    patch("cwbridge.ytd_index.convert_file", side_effect=convert) as bridge:
                first = index_ytd_directory(source, cache, progress_callback=lambda *args: progress.append(args))
                second = index_ytd_directory(source, cache)
                self.assertEqual(bridge.call_count, 1)
                first.textures[0].path.unlink()
                index_ytd_directory(source, cache)
                index_ytd_directory(source, cache, force_reindex=True)

            self.assertEqual(first.indexed_dictionaries, 1)
            self.assertEqual([item.name for item in first.textures], ["diffuse"])
            self.assertEqual([item.name for item in second.textures], ["diffuse"])
            self.assertEqual(bridge.call_count, 3)
            self.assertEqual(progress, [(0, 1), (1, 1)])

    def test_uses_non_recursive_scan_when_requested(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            nested = source / "nested"
            nested.mkdir(parents=True)
            (source / "top.ytd").touch()
            (nested / "nested.ytd").touch()

            def convert(input_path, output, **_kwargs):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text("<TextureDictionary />", encoding="utf-8")
                return {"ok": True, "outputPath": str(output)}

            with patch("cwbridge.ytd_index.find_bridge_command", return_value=["bridge"]), \
                    patch("cwbridge.ytd_index.convert_file", side_effect=convert) as bridge:
                result = index_ytd_directory(source, root / "cache", recursive=False)

            self.assertEqual(result.indexed_dictionaries, 1)
            self.assertEqual(bridge.call_count, 1)
            self.assertEqual(Path(bridge.call_args.args[0]).name, "top.ytd")

    def test_cancels_before_indexing_ytds(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "model.ytd").touch()
            cancel_event = threading.Event()
            cancel_event.set()

            with patch("cwbridge.ytd_index.find_bridge_command", return_value=["bridge"]):
                with self.assertRaisesRegex(CWBridgeCancelled, "cancelled"):
                    index_ytd_directory(root, root / "cache", cancel_event=cancel_event)

    def test_chooses_model_named_dictionary_and_skips_ambiguous_matches(self):
        candidates = (
            IndexedTexture("diffuse", Path("one/diffuse.dds"), "model_a"),
            IndexedTexture("diffuse", Path("two/diffuse.dds"), "model_b"),
        )

        self.assertEqual(
            choose_texture(candidates, "diffuse", ["model_b.ydr"]),
            candidates[1],
        )
        self.assertIsNone(choose_texture(candidates, "diffuse", ["unrelated_model"]))
        self.assertIsNone(choose_texture(candidates, "missing", ["model_b"]))


class XmlImportStagingTests(unittest.TestCase):
    def test_stages_textures_from_sollumz_asset_subdirectory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml_path = root / "model.ydr.xml"
            texture_directory = root / "model"
            texture_directory.mkdir()
            texture = texture_directory / "diffuse.dds"
            texture.write_bytes(b"DDS fixture")
            xml_path.write_text(
                "<Drawable><FileName>diffuse.dds</FileName><FileName>shader.sps</FileName></Drawable>",
                encoding="utf-8",
            )

            staged_xml = stage_xml_for_import(xml_path, root / "staging", "ydr")

            self.assertEqual(staged_xml.read_text(encoding="utf-8"), xml_path.read_text(encoding="utf-8"))
            self.assertEqual((staged_xml.parent / "diffuse.dds").read_bytes(), b"DDS fixture")
            self.assertEqual(
                (staged_xml.parent / "model" / "diffuse.dds").read_bytes(),
                b"DDS fixture",
            )
            self.assertFalse((staged_xml.parent / "shader.sps").exists())

    def test_rejects_texture_paths_escaping_xml_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml_path = root / "model.xml"
            xml_path.write_text(
                "<Drawable><FileName>../outside.dds</FileName></Drawable>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CWBridgeError, "Unsafe texture path"):
                stage_xml_for_import(xml_path, root / "staging", "ydr")

    def test_reports_missing_referenced_texture(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xml_path = root / "model.xml"
            xml_path.write_text(
                "<Drawable><FileName>missing.dds</FileName></Drawable>",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(CWBridgeError, "Referenced texture file not found"):
                stage_xml_for_import(xml_path, root / "staging", "ydr")


class YtdIndexAdditionalTests(unittest.TestCase):
    def test_prefers_high_resolution_dictionary_variant(self):
        candidates = (
            IndexedTexture("diffuse", Path("base/diffuse.dds"), "model"),
            IndexedTexture("diffuse", Path("hi/diffuse.dds"), "model+hi"),
        )

        self.assertEqual(choose_texture(candidates, "diffuse", ["model.ydr"]), candidates[1])

    def test_requires_bridge_even_for_empty_directory(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch(
                "cwbridge.ytd_index.find_bridge_command",
                side_effect=CWBridgeError("bridge missing"),
            ):
                with self.assertRaisesRegex(CWBridgeError, "bridge missing"):
                    index_ytd_directory(root, root / "cache")

    def test_rejects_texture_paths_escaping_cache(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "model.ytd").write_bytes(b"fixture")

            def convert(_input, output, **_kwargs):
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(
                    "<TextureDictionary><Item><FileName>../outside.dds</FileName></Item></TextureDictionary>",
                    encoding="utf-8",
                )
                return {"ok": True, "outputPath": str(output)}

            with patch("cwbridge.ytd_index.find_bridge_command", return_value=["bridge"]), \
                    patch("cwbridge.ytd_index.convert_file", side_effect=convert):
                result = index_ytd_directory(source, root / "cache")

            self.assertEqual(result.indexed_dictionaries, 0)
            self.assertIn("unsafe texture path", result.errors[0])
            self.assertFalse((root / "outside.dds").exists())


if __name__ == "__main__":
    unittest.main()
