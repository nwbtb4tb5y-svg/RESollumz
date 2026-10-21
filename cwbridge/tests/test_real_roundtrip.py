import tempfile
import unittest
from collections import Counter
from pathlib import Path
from xml.etree import ElementTree

from cwbridge.client import CWBridgeError, convert_file, find_bridge_command


ASSET_ROOT = Path(__file__).resolve().parents[2] / "tests" / "assets"
SEMANTIC_ITEM_CONTAINERS = {
    "DrawableModelsHigh",
    "DrawableModelsMedium",
    "DrawableModelsLow",
    "DrawableModelsVeryLow",
    "Drawables",
    "Geometries",
    "Shaders",
    "TextureDictionary",
}


def summarize_xml(path: Path) -> tuple[Counter[str], tuple[str, ...], tuple[str, ...], dict[str, int]]:
    root = ElementTree.parse(path).getroot()
    tag_counts = Counter(element.tag for element in root.iter() if element.tag != "Item")
    names = tuple(element.text or "" for element in root.iter("Name"))
    filenames = tuple(element.text or "" for element in root.iter("FileName"))
    semantic_items = {
        container.tag: sum(child.tag == "Item" for child in container)
        for container in root.iter()
        if container.tag in SEMANTIC_ITEM_CONTAINERS
    }
    return tag_counts, names, filenames, semantic_items


class RealCWBridgeRoundtripTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            find_bridge_command()
        except CWBridgeError as exc:
            raise unittest.SkipTest(f"CWBridge is not available: {exc}") from exc

    def test_available_gen8_and_gen9_asset_roundtrips(self):
        fixtures = sorted(
            path
            for generation in ("gen8", "gen9")
            for path in (ASSET_ROOT / generation).iterdir()
            if path.suffix.lower() in {".ydr", ".yft", ".ydd", ".ytd"}
        )
        self.assertTrue(fixtures, "No binary CWBridge fixtures were found.")

        with tempfile.TemporaryDirectory(prefix="cwbridge-roundtrip-") as temporary:
            root = Path(temporary)
            for fixture in fixtures:
                with self.subTest(fixture=str(fixture.relative_to(ASSET_ROOT))):
                    is_gen9 = fixture.parent.name == "gen9"
                    case_directory = root / f"{fixture.parent.name}_{fixture.stem}"
                    export_directory = case_directory / "export"
                    reexport_directory = case_directory / "reexport"
                    export_directory.mkdir(parents=True)
                    reexport_directory.mkdir()
                    xml_path = export_directory / f"{fixture.stem}.xml"
                    binary_path = case_directory / f"roundtrip{fixture.suffix}"
                    reexport_path = reexport_directory / f"{fixture.stem}.xml"

                    convert_file(fixture, xml_path, operation="to_xml", gen9=is_gen9)
                    original = summarize_xml(xml_path)
                    convert_file(xml_path, binary_path, operation="from_xml", gen9=is_gen9)
                    convert_file(binary_path, reexport_path, operation="to_xml", gen9=is_gen9)
                    roundtrip = summarize_xml(reexport_path)

                    self.assertEqual(original[0], roundtrip[0], "XML element structure changed.")
                    self.assertEqual(original[1], roundtrip[1], "Named resources changed.")
                    self.assertEqual(original[2], roundtrip[2], "Texture file references changed.")
                    self.assertEqual(original[3], roundtrip[3], "Model, material, geometry, or texture counts changed.")


if __name__ == "__main__":
    unittest.main()
