import bpy


_TRANSLATIONS = {
    "pt_BR": {
        ("*", "Enable CWBridge Features"): "Ativar recursos do CWBridge",
        ("*", "Import CodeWalker Model to Scene"): "Importar modelo do CodeWalker para a cena",
        ("*", "Export CodeWalker XML (.yft.xml)"): "Exportar XML do CodeWalker (.yft.xml)",
        ("*", "Export YFT via CodeWalker (with backup)"):
            "Exportar YFT pelo CodeWalker (com backup)",
        ("*", "Replace an existing YFT with the selected Sollumz fragment."):
            "Substituir um YFT existente pelo fragmento Sollumz selecionado.",
        ("*", "A .backup copy of the original file will be kept."):
            "Uma cópia .backup do arquivo original será mantida.",
        ("*", "Select an existing .yft file to replace."):
            "Selecione um arquivo .yft existente para substituir.",
        ("*", "Select exactly one Sollumz Fragment to export as a YFT."):
            "Selecione exatamente um fragmento Sollumz para exportar como YFT.",
        ("*", "YFT updated. Original backup created."):
            "YFT atualizado. Backup original criado.",
        ("*", "Expected one exported YFT XML file, found {}."):
            "Era esperado um XML YFT exportado, mas foram encontrados {}.",
        ("*", "Import a CodeWalker model or XML file into the current scene"):
            "Importar um modelo ou arquivo XML do CodeWalker para a cena atual",
        ("*", "Export selected models as CodeWalker XML (.yft.xml)."):
            "Exportar os modelos selecionados como XML do CodeWalker (.yft.xml).",
        ("*", "Find Textures in YTD Folder"): "Buscar texturas em pasta YTD",
        ("*", "Find in Shared Texture Folders"): "Buscar nas pastas compartilhadas de texturas",
        ("*", "Search Subfolders"): "Buscar em subpastas",
        ("*", "Reindex YTD Files"): "Reindexar arquivos YTD",
        ("*", "Select an existing CodeWalker model or XML file."):
            "Selecione um modelo ou arquivo XML existente do CodeWalker.",
        ("*", "Supported XML resources are YDR, YFT, YDD, and YTD."):
            "Os recursos XML suportados são YDR, YFT, YDD e YTD.",
        ("*", "Enable CWBridge Features in Sollumz preferences first."):
            "Ative os recursos do CWBridge nas preferências do Sollumz.",
        ("*", "Cancelling CodeWalker conversion..."): "Cancelando conversão do CodeWalker...",
        ("*", "CodeWalker conversion cancelled."): "Conversão do CodeWalker cancelada.",
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
