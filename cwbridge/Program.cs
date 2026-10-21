using System.Text.Json;
using CodeWalker.GameFiles;

namespace RESollumz.CWBridge;

internal static class Program
{
    private static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNameCaseInsensitive = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    private static async Task<int> Main()
    {
        var standardOutput = Console.Out;
        string input;
        try
        {
            input = await Console.In.ReadToEndAsync();
        }
        catch (Exception exception)
        {
            return WriteError(standardOutput, "request_read_failed", exception);
        }

        Console.SetOut(TextWriter.Null);
        try
        {
            var request = JsonSerializer.Deserialize<BridgeRequest>(input, JsonOptions)
                ?? throw new BridgeException("invalid_request", "The JSON request must be an object.");
            var response = Process(request);
            standardOutput.WriteLine(JsonSerializer.Serialize(response, JsonOptions));
            return 0;
        }
        catch (JsonException exception)
        {
            return WriteError(standardOutput, "invalid_json", exception);
        }
        catch (BridgeException exception)
        {
            return WriteError(standardOutput, exception.Code, exception);
        }
        catch (Exception exception)
        {
            return WriteError(standardOutput, "conversion_failed", exception);
        }
        finally
        {
            Console.SetOut(standardOutput);
        }
    }

    private static object Process(BridgeRequest request)
    {
        var operation = request.Operation?.Trim().ToLowerInvariant();
        if (operation is not ("to_xml" or "from_xml"))
        {
            throw new BridgeException("invalid_operation", "Operation must be 'to_xml' or 'from_xml'.");
        }

        var inputPath = GetRequiredPath(request.InputPath, "inputPath");
        var outputPath = GetRequiredPath(request.OutputPath, "outputPath");
        if (!File.Exists(inputPath))
        {
            throw new BridgeException("input_not_found", $"Input file does not exist: {inputPath}");
        }
        if (string.Equals(inputPath, outputPath, StringComparison.OrdinalIgnoreCase))
        {
            throw new BridgeException("same_input_output", "Input and output paths must be different.");
        }
        if (File.Exists(outputPath))
        {
            throw new BridgeException("output_exists", $"Output file already exists: {outputPath}");
        }

        var format = operation == "to_xml"
            ? GetFormat(Path.GetExtension(inputPath))
            : GetFormat(Path.GetExtension(outputPath));
        if (operation == "to_xml" && !Path.GetExtension(outputPath).Equals(".xml", StringComparison.OrdinalIgnoreCase))
        {
            throw new BridgeException("invalid_output_format", "The output path for 'to_xml' must end in .xml.");
        }
        if (operation == "from_xml" && !Path.GetExtension(inputPath).Equals(".xml", StringComparison.OrdinalIgnoreCase))
        {
            throw new BridgeException("invalid_input_format", "The input path for 'from_xml' must end in .xml.");
        }

        RpfManager.IsGen9 = request.Gen9;
        Directory.CreateDirectory(Path.GetDirectoryName(outputPath)!);
        if (operation == "to_xml")
        {
            ExportXml(format, inputPath, outputPath, request.IncludeTextures);
        }
        else
        {
            ImportXml(format, inputPath, outputPath);
        }

        return new BridgeResponse(true, operation, format, outputPath, null, request.Gen9);
    }

    private static void ExportXml(string format, string inputPath, string outputPath, bool includeTextures)
    {
        var input = File.ReadAllBytes(inputPath);
        var assetDirectory = Path.GetDirectoryName(outputPath)!;
        var stagingDirectory = Path.Combine(assetDirectory, $".cwbridge-{Guid.NewGuid():N}");
        Directory.CreateDirectory(stagingDirectory);
        var stagedOutput = Path.Combine(stagingDirectory, Path.GetFileName(outputPath));
        try
        {
            var xml = format switch
            {
                "ydr" => ExportYdr(input, includeTextures ? stagingDirectory : string.Empty),
                "yft" => ExportYft(input, includeTextures ? stagingDirectory : string.Empty),
                "ydd" => ExportYdd(input, includeTextures ? stagingDirectory : string.Empty),
                "ytd" => ExportYtd(input, includeTextures ? stagingDirectory : string.Empty),
                _ => throw new BridgeException("unsupported_format", $"Unsupported resource format: {format}"),
            };
            File.WriteAllText(stagedOutput, xml, new System.Text.UTF8Encoding(false));
            PublishExport(stagingDirectory, assetDirectory);
        }
        finally
        {
            Directory.Delete(stagingDirectory, recursive: true);
        }
    }

    private static string ExportYdr(byte[] input, string textureDirectory)
    {
        var file = new YdrFile();
        file.Load(input);
        ValidateTextureDictionary(file.Drawable?.ShaderGroup?.TextureDictionary);
        return YdrXml.GetXml(file, textureDirectory);
    }

    private static string ExportYft(byte[] input, string textureDirectory)
    {
        var file = new YftFile();
        file.Load(input);
        ValidateTextureDictionary(file.Fragment?.Drawable?.ShaderGroup?.TextureDictionary);
        ValidateTextureDictionary(file.Fragment?.DrawableCloth?.ShaderGroup?.TextureDictionary);
        return YftXml.GetXml(file, textureDirectory);
    }

    private static string ExportYdd(byte[] input, string textureDirectory)
    {
        var file = new YddFile();
        file.Load(input);
        foreach (var drawable in file.DrawableDict?.Drawables?.data_items ?? Array.Empty<Drawable>())
        {
            ValidateTextureDictionary(drawable?.ShaderGroup?.TextureDictionary);
        }
        return YddXml.GetXml(file, textureDirectory);
    }

    private static string ExportYtd(byte[] input, string textureDirectory)
    {
        var file = new YtdFile();
        file.Load(input);
        ValidateTextureDictionary(file.TextureDict);
        return YtdXml.GetXml(file, textureDirectory);
    }

    private static void ValidateTextureDictionary(TextureDictionary? dictionary)
    {
        foreach (var texture in dictionary?.Textures?.data_items ?? Array.Empty<Texture>())
        {
            var name = texture.Name;
            if (string.IsNullOrWhiteSpace(name)
                || name is "." or ".."
                || name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0
                || Path.GetFileName(name) != name
                || name.Contains('/') || name.Contains('\\'))
            {
                throw new BridgeException("unsafe_texture_name", $"Texture name cannot be safely exported as a filename: {name}");
            }
        }
    }

    private static void ImportXml(string format, string inputPath, string outputPath)
    {
        var xml = File.ReadAllText(inputPath);
        var inputDirectory = Path.GetDirectoryName(inputPath)!;
        var binary = format switch
        {
            "ydr" => XmlYdr.GetYdr(xml, inputDirectory).Save(),
            "yft" => XmlYft.GetYft(xml, inputDirectory).Save(),
            "ydd" => XmlYdd.GetYdd(xml, inputDirectory).Save(),
            "ytd" => XmlYtd.GetYtd(xml, inputDirectory).Save(),
            _ => throw new BridgeException("unsupported_format", $"Unsupported resource format: {format}"),
        };

        WriteNewFile(outputPath, binary);
    }

    private static string GetRequiredPath(string? value, string field)
    {
        if (string.IsNullOrWhiteSpace(value))
        {
            throw new BridgeException("invalid_request", $"'{field}' is required.");
        }
        return Path.GetFullPath(value);
    }

    private static string GetFormat(string extension)
    {
        var format = extension.TrimStart('.').ToLowerInvariant();
        if (format is not ("ydr" or "yft" or "ydd" or "ytd"))
        {
            throw new BridgeException(
                "unsupported_format",
                $"Unsupported resource format '{extension}'. Supported formats: .ydr, .yft, .ydd, .ytd.");
        }
        return format;
    }

    private static void WriteNewFile(string path, byte[] contents)
    {
        var temporaryPath = Path.Combine(
            Path.GetDirectoryName(path)!,
            $".cwbridge-{Guid.NewGuid():N}.tmp");
        try
        {
            using (var stream = new FileStream(temporaryPath, FileMode.CreateNew, FileAccess.Write, FileShare.None))
            {
                stream.Write(contents);
                stream.Flush(true);
            }
            File.Move(temporaryPath, path);
        }
        finally
        {
            if (File.Exists(temporaryPath))
            {
                File.Delete(temporaryPath);
            }
        }
    }

    private static void PublishExport(string stagingDirectory, string destinationDirectory)
    {
        var stagedFiles = Directory.GetFiles(stagingDirectory, "*", SearchOption.AllDirectories);
        var destinations = stagedFiles.Select(path =>
        {
            var relativePath = Path.GetRelativePath(stagingDirectory, path);
            if (Path.IsPathRooted(relativePath)
                || relativePath == ".."
                || relativePath.StartsWith($"..{Path.DirectorySeparatorChar}", StringComparison.Ordinal)
                || relativePath.StartsWith($"..{Path.AltDirectorySeparatorChar}", StringComparison.Ordinal))
            {
                throw new BridgeException("unsafe_export_path", "CodeWalker generated a file outside the export directory.");
            }
            return (Source: path, Destination: Path.GetFullPath(Path.Combine(destinationDirectory, relativePath)));
        }).ToArray();

        var duplicateDestination = destinations
            .GroupBy(item => item.Destination, StringComparer.OrdinalIgnoreCase)
            .FirstOrDefault(group => group.Count() > 1);
        if (duplicateDestination is not null)
        {
            throw new BridgeException("export_collision", "Multiple generated files have the same destination path.");
        }

        var existing = destinations.FirstOrDefault(item => File.Exists(item.Destination));
        if (existing.Destination is not null)
        {
            throw new BridgeException("output_exists", $"Export would overwrite an existing file: {existing.Destination}");
        }

        var published = new List<string>();
        try
        {
            foreach (var item in destinations)
            {
                Directory.CreateDirectory(Path.GetDirectoryName(item.Destination)!);
                File.Move(item.Source, item.Destination);
                published.Add(item.Destination);
            }
        }
        catch
        {
            foreach (var path in published)
            {
                File.Delete(path);
            }
            throw;
        }
    }

    private static int WriteError(TextWriter output, string code, Exception exception)
    {
        Console.Error.WriteLine(exception);
        output.WriteLine(JsonSerializer.Serialize(
            new BridgeResponse(false, null, null, null, new BridgeError(code, exception.Message), null),
            JsonOptions));
        return 1;
    }

    private sealed class BridgeRequest
    {
        public string? Operation { get; init; }
        public string? InputPath { get; init; }
        public string? OutputPath { get; init; }
        public bool Gen9 { get; init; }
        public bool IncludeTextures { get; init; } = true;
    }

    private sealed record BridgeResponse(
        bool Ok,
        string? Operation,
        string? Format,
        string? OutputPath,
        BridgeError? Error,
        bool? Gen9);

    private sealed record BridgeError(string Code, string Message);

    private sealed class BridgeException(string code, string message) : Exception(message)
    {
        public string Code { get; } = code;
    }
}
