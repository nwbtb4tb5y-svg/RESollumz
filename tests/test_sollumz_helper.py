from types import SimpleNamespace

from .. import sollumz_helper
from ..sollumz_properties import MaterialType, SollumType


def test_get_sollumz_materials_skips_empty_slots(monkeypatch):
    class FakeMaterial:
        sollum_type = MaterialType.SHADER
        shader_properties = SimpleNamespace(index=0)

    material = FakeMaterial()
    model = SimpleNamespace(
        sollum_type=SollumType.DRAWABLE_MODEL,
        sz_lods=SimpleNamespace(
            get_lod=lambda _lod_level: SimpleNamespace(
                mesh=SimpleNamespace(materials=[None, material])
            )
        ),
    )
    monkeypatch.setattr(sollumz_helper, "get_children_recursive", lambda _obj: [model])

    assert sollumz_helper.get_sollumz_materials(SimpleNamespace()) == [material]
