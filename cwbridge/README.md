# CWBridge

CWBridge is a small JSON-over-stdin console wrapper around the vendored `CodeWalker.Core` library. It converts loose GTA V `.ydr`, `.yft`, `.ydd` and `.ytd` resources to/from CodeWalker's XML representation. It does not open RPF archives or require game installation paths.

## Build

From the repository root, with the .NET 8 SDK installed:

```powershell
dotnet build cwbridge\CWBridge.csproj --configuration Release
```

The project references `RECodeWalker\CodeWalker.Core` at the pinned submodule revision. For a fresh checkout, initialize it with `git submodule update --init --recursive`. Package restore requires NuGet access for CodeWalker's SharpDX dependencies. The framework-dependent build requires the .NET 8 runtime to run. To publish the self-contained Windows x64 executable and place the required third-party notices beside it, run:

```powershell
.\cwbridge\publish.ps1
```

The RESollumz Prototype package includes the self-contained executable and third-party notices under `cwbridge\publish\`. In Blender, set **CWBridge Executable** in Sollumz preferences to a published executable or the built `CWBridge.dll`. On Windows the DLL requires the .NET 8 runtime on `PATH`; a self-contained executable does not. The source checkout build is also detected automatically.

CodeWalker source is maintained in the [RECodeWalker submodule](../RECodeWalker) at a pinned commit. The CodeWalker project describes its source as released for educational purposes; RESollumz's bundled bridge is distributed under separate written authorization from the rights holders. See [THIRD_PARTY_NOTICES.md](./THIRD_PARTY_NOTICES.md) for redistribution notices.

## Protocol

Send one JSON object to standard input. CWBridge writes exactly one JSON response to standard output; diagnostics go to standard error. Paths are local filesystem paths. Existing output files are not overwritten.

Binary resource to XML:

```json
{
  "operation": "to_xml",
  "inputPath": "C:\\assets\\model.ydr",
  "outputPath": "C:\\assets\\model.xml",
  "gen9": false,
  "includeTextures": true
}
```

XML to binary resource:

```json
{
  "operation": "from_xml",
  "inputPath": "C:\\assets\\model.xml",
  "outputPath": "C:\\assets\\model.ydr",
  "gen9": false
}
```

`gen9` defaults to `false`. `includeTextures` defaults to `true`; when exporting, CodeWalker writes texture DDS files next to the XML. The import operation resolves referenced DDS files relative to the XML file's directory.

Success response:

```json
{"ok":true,"operation":"to_xml","format":"ydr","outputPath":"C:\\assets\\model.xml","error":null,"gen9":false}
```

Failure response:

```json
{"ok":false,"operation":null,"format":null,"outputPath":null,"error":{"code":"input_not_found","message":"Input file does not exist: ..."},"gen9":null}
```

The process exits with status `0` on success and `1` on failure. Supported error codes include `invalid_json`, `invalid_request`, `invalid_operation`, `unsupported_format`, `invalid_input_format`, `invalid_output_format`, `input_not_found`, `output_exists`, `same_input_output`, `unsafe_texture_name`, `unsafe_export_path`, `export_collision` and `conversion_failed`.

## Blender YTD lookup

The YTD tool panel provides **Find Textures in YTD Folder**. Select a model with unresolved Sollumz texture samplers, choose a folder, and choose Gen8 or Gen9. The add-on scans `.ytd` files recursively, uses CWBridge to extract texture DDS files into Blender's user configuration cache, and links unambiguous name matches to the selected model's material samplers. A YTD whose name matches the model is preferred; `+hi` dictionaries are preferred within that match. Existing, packed, or non-file images are left unchanged, and ambiguous names are not linked automatically.

The index cache is refreshed when the source YTD size, modification time, or selected generation changes. Failed dictionaries are reported while other files continue to be indexed. When a shared folder contains mixed-generation resources, choose the matching generation; incompatible dictionaries are reported as errors.

Importing the converted binary into Blender requires PyMateria, Sollumz's optional native dependency. The XML-to-binary conversion can succeed without it, but the Blender importer cannot load the binary resource.
