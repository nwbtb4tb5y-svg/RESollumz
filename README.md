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

Blender plugin to import, export, or create GTA V assets.

By Skylumz, Colton Fox and alexguirre.

## Join our Discord
Join the Sollumz [discord server](https://discord.sollumz.org/) to ask questions and chat with the community!
## Using the plugin
See the [wiki](https://docs.sollumz.org/) to get started. Make sure to read the wiki before posting an issue or asking questions! Also, see the Tutorials and Resources channel on the Discord server.

**Note:** The issue tracker should be for bug reports and feature requests only. If you are having an issue and you are not sure if it is a bug or not, ask on the Discord server first!

## Features ##

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

## Requirements ##
  * [Blender 4.2 or newer](http://www.blender.org/download/)
  * Recommended: latest CodeWalker release from [their discord](https://discord.gg/codewalker)

## Installation ##

Follow the [installation instructions on our wiki](https://docs.sollumz.org/getting-started/installation).

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
