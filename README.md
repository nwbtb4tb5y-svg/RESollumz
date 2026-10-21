# RESollumz Prototype

RESollumz is an experimental Sollumz fork for Blender, maintained by `nwbtb4tb5y-svg`. It preserves the upstream Sollumz workflow and adds an independent release loader and optional CodeWalker integration.

This prototype is based on [Sollumz](https://github.com/Sollumz/Sollumz), by Skylumz, Colton Fox and alexguirre. See [LICENSE](./LICENSE) for the project license and attribution.

## Build and package

Clone with `git clone --recurse-submodules` or initialize the CodeWalker dependency in an existing checkout with `git submodule update --init --recursive`. The CWBridge project requires the .NET 8 SDK; run `.\cwbridge\publish.ps1` to publish its self-contained Windows x64 executable and copy its third-party notices. With Blender 5.2.2 available on `PATH`, build the installable packages from the repository root:

```powershell
New-Item -ItemType Directory -Path .\dist -Force | Out-Null
Remove-Item -LiteralPath .\dist\resollumz-0.1.0.zip,.\dist\resollumz_loader-0.1.0.zip -Force -ErrorAction SilentlyContinue
blender --command extension build --source-dir . --output-dir dist
blender --command extension build --source-dir .\resollumz_loader --output-dir dist
```

The existing ZIPs are removed before rebuilding because Blender's extension builder appends to an output archive if it already exists. The main extension package targets Windows x64 because it bundles CWBridge. The loader is a separate, platform-independent package. See [CWBridge third-party notices](./cwbridge/THIRD_PARTY_NOTICES.md) for bundled dependency attributions.

## RESollumz additions

- **RESollumz Loader** (`resollumz_loader/`) installs and selects official Sollumz releases side by side. Switching an already active release requires restarting Blender.
- **CWBridge** converts loose YDR, YFT, YDD and YTD resources between binary and CodeWalker XML formats.
- The Blender import menu can convert CodeWalker XML to binary and pass the result to the existing Sollumz importer.
- The Texture Dictionaries panel can find matching textures in selected YTD folders or shared texture directories, with Gen8/Gen9 selection, a persistent extraction cache, progress and cancellation.

CWBridge integration is controlled by **Enable CWBridge Features** in Sollumz Preferences. The self-contained Windows x64 bridge is bundled with the prototype package. Importing binary resources into Blender also requires the optional PyMateria dependency; the bridge conversion alone does not install PyMateria.

See [cwbridge/README.md](./cwbridge/README.md) for bridge setup, protocol and YTD lookup details, and [resollumz_loader/README.md](./resollumz_loader/README.md) for loader behavior and compatibility.

## Prototype limitations

- The checked-in fixtures cover Gen8/Gen9 YDR, cloth YFT and YTD, but do not include YDD or vehicle YFT resources.
- Blender validation was performed on 5.2.2; Blender 4.2 and interactive UI workflows still need manual testing.
- CodeWalker round-trips preserve tested model, geometry, shader and texture counts but normalize some shader parameters and shader-name hashes; they are not byte-identical.
- The loader requires a Blender restart to switch an active release safely.

## Installation and getting started

RESollumz follows the Sollumz workflows, but some upstream wiki installation steps do not apply to this fork. Keep the original [Sollumz wiki](https://docs.sollumz.org/) for general modeling and asset-authoring guidance; use the fork-specific instructions below to install and use RESollumz features.

### Requirements

- Blender 4.2 or newer. The packaged release was validated with Blender 5.2.2.
- Windows x64 to use the bundled CWBridge tools. The main extension package includes a self-contained CWBridge executable; a separate CodeWalker installation and .NET runtime are not required.
- PyMateria, Sollumz's optional native dependency, is required for the usual native-binary import/export providers. The CodeWalker model importer instead converts `.ydr`, `.yft`, `.ydd`, and `.ytd` inputs to temporary CWXML and imports that XML through Sollumz.

### Install the RESollumz add-on

1. Download `resollumz-0.1.0.zip` from the [RESollumz Prototype release](https://github.com/nwbtb4tb5y-svg/RESollumz/releases/tag/v0.1.0). Keep the ZIP intact; do not extract it.
2. In Blender, open **Edit > Preferences > Get Extensions** and choose **Install from Disk**.
3. Select the downloaded ZIP. Find **RESollumz** in the installed extensions list and enable it.
4. If the upstream Sollumz add-on is already enabled, disable it and restart Blender before enabling RESollumz. The two add-ons register overlapping Blender types and should not be active together.
5. To enable CodeWalker tools, open **Edit > Preferences > Add-ons > RESollumz**, expand the **Import** settings, and leave **Enable CWBridge Features** enabled. The released Windows package already includes CWBridge, so the **CWBridge Executable** path can normally be left blank.

### Optional: install RESollumz Loader

The Loader is a separate extension for downloading and managing official Sollumz releases; it is not required to use the RESollumz add-on.

1. Download `resollumz_loader-0.1.0.zip` from the same [release](https://github.com/nwbtb4tb5y-svg/RESollumz/releases/tag/v0.1.0).
2. Install it with **Edit > Preferences > Get Extensions > Install from Disk**, then enable **RESollumz Loader**.
3. Open the Loader preferences, allow network access if Blender asks, refresh the release list, and choose an official Sollumz release to install.
4. The Loader cannot safely switch an already active Sollumz version in the current Blender process. Restart Blender to activate a different managed release. If RESollumz or another Sollumz add-on is enabled, the Loader skips automatic activation of its managed release to avoid registering two versions at once.

### Use the RESollumz features

**Import CodeWalker models into the scene**

1. Make sure **Enable CWBridge Features** is enabled in RESollumz preferences.
2. Choose **File > Import > Import CodeWalker Model to Scene**.
3. Select the original `.ydr`, `.yft`, `.ydd`, or `.ytd` model and select **Gen9** only for GTA V Enhanced resources.
4. RESollumz uses CWBridge to create temporary CodeWalker XML and imports it through Sollumz. No manual XML export or PyMateria binary-import step is needed; the temporary files are removed after import.

**Export models as CodeWalker XML**

1. Select the Sollumz model objects to export.
2. Choose **File > Export > Export CodeWalker XML (.yft.xml)**.
3. Select the output folder and the target game version. Sollumz writes CodeWalker XML files such as `model.yft.xml`; the existing model files are not overwritten.

**Find textures in YTD dictionaries**

1. Select the model or models whose Sollumz texture samplers have missing images.
2. In the 3D Viewport, open the **Sollumz Tools** sidebar tab (press **N** if the sidebar is hidden) and expand **Texture Dictionaries**.
3. Choose **Find Textures in YTD Folder** to select a folder, or **Find in Shared Texture Folders** to search the shared texture directories configured in RESollumz preferences.
4. Select **Gen9** only when the YTD files are from GTA V Enhanced. Optionally enable **Reindex YTD Files** to extract the dictionaries again instead of reusing valid cache entries. For a selected folder, **Search Subfolders** controls recursive scanning.
5. Wait for indexing to finish. Matching, unambiguous textures are linked automatically; existing images are preserved and ambiguous matches are skipped. Progress and per-dictionary errors are reported in Blender.

Normal Sollumz import, export, and asset-editing workflows remain available. The original [Sollumz wiki](https://docs.sollumz.org/) and [Discord server](https://discord.sollumz.org/) provide general community guidance, but use this README and the [CWBridge guide](./cwbridge/README.md) for RESollumz-specific setup and behavior.

## Features

**Supported Formats**
  * YDD
  * YDR
  * YFT
  * YBN
  * YTYP
  * YCD
  * YMAP (Partial)

**General Features**
  * Import / Export
  * Automatic texture loading
  * Vertex colors
  * Bones and weights
  * Animations
  * Custom normals
  * Shader editing
  * Vehicle creation/editing
  * Dynamic prop creation/editing

---

### Supporters ❤️ ###

A big thank you to all of our supporters, including:

- Code contributors on [GitHub](https://github.com/Sollumz/Sollumz/graphs/contributors).
- Financial contributors on [Open Collective](https://opencollective.com/sollumz) and [GitHub Sponsors](https://github.com/sponsors/Sollumz).
- dexyfex and the [CodeWalker](https://github.com/dexyfex/CodeWalker) contributors.
- Our wiki host [GitBook](https://www.gitbook.com/).

---

## License

Copyright (C) 2020-2025 Skylumz, Colton and alexguirre

This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the [GNU General Public License](./LICENSE) for more details.

You should have received a copy of the GNU General Public License along with this program. If not, see <https://www.gnu.org/licenses/>.
