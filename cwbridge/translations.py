import bpy


_TRANSLATIONS = {
    "pt_BR": {
        ("*", "Enable CWBridge Features"): "Ativar recursos do CWBridge",
        ("*", "Import CodeWalker XML to Scene"): "Importar XML do CodeWalker para a cena",
        ("*", "Convert CodeWalker XML to a binary asset and import it into the current scene"):
            "Converter o XML do CodeWalker para binário e importá-lo na cena atual",
        ("*", "Find Textures in YTD Folder"): "Buscar texturas em pasta YTD",
        ("*", "Find in Shared Texture Folders"): "Buscar nas pastas compartilhadas de texturas",
        ("*", "Search Subfolders"): "Buscar em subpastas",
        ("*", "Reindex YTD Files"): "Reindexar arquivos YTD",
        ("*", "Select an existing CodeWalker XML file."): "Selecione um arquivo XML válido do CodeWalker.",
        ("*", "Supported XML resources are YDR, YFT, YDD, and YTD."):
            "Os recursos XML suportados são YDR, YFT, YDD e YTD.",
        ("*", "Enable CWBridge Features in Sollumz preferences first."):
            "Ative os recursos do CWBridge nas preferências do Sollumz.",
        ("*", "Cancelling XML conversion..."): "Cancelando a conversão XML...",
        ("*", "XML conversion cancelled."): "Conversão XML cancelada.",
        ("*", "Cancelling YTD indexing..."): "Cancelando a indexação de YTD...",
        ("*", "YTD indexing cancelled."): "Indexação de YTD cancelada.",
        ("*", "Find Textures in Shared Folders"): "Buscar texturas nas pastas compartilhadas",
        ("*", "Add an existing Shared Textures directory in Sollumz preferences first."):
            "Adicione uma pasta compartilhada de texturas existente nas preferências do Sollumz.",
    },
}


def register():
    bpy.app.translations.register("resollumz_cwbridge", _TRANSLATIONS)


def unregister():
    bpy.app.translations.unregister("resollumz_cwbridge")
