# RESollumz Loader

RESollumz Loader is a small Blender extension for installing and selecting official Sollumz releases. It is separate from the Sollumz source tree in the parent directory; installing the loader does not install or activate that source tree.

## Requirements

- Blender 4.2 or newer.
- Network access is optional. Enable **Allow network access** in the loader preferences before refreshing releases or downloading a release. On Blender versions that expose `bpy.app.online_access`, Blender's own online-access setting must also allow requests.

## Install

Install this directory as a Blender extension (`resollumz_loader/blender_manifest.toml`) or package its contents as an extension ZIP. Enable **RESollumz Loader**, open its add-on preferences, refresh the release list, select a tag, and choose **Download / Install and Activate**.

Downloads are initiated only by the user. The loader prefers the official `Sollumz.zip` release asset, checks a published SHA-256 digest, and validates archive paths before extraction. Older releases without a published digest are installed with a warning. Installed versions are kept side by side under Blender's user configuration directory at `resollumz/versions/`; release metadata is cached there for offline use. To raise GitHub API rate limits, optionally set `GITHUB_TOKEN` in the environment before starting Blender. The token is not stored in Blender preferences.

The loader stores the selected release and activates it on Blender startup. If no Sollumz version is already active, selecting a version can load it immediately. Switching away from an active release requires restarting Blender: upstream releases register Blender classes, properties, handlers and dependencies that cannot be safely unloaded in the general case. This conservative fallback avoids leaving a partially registered add-on or unloading native libraries in use.

## Compatibility

The loader targets Blender 4.2+. It handles both legacy add-on ZIPs and extension-era `Sollumz.zip` assets by locating the packaged `Sollumz/__init__.py`. The managed package uses a private Python package namespace, and its dependency data directory is isolated per release. Blender preferences belonging to Sollumz remain available through the managed namespace and may need to be configured again after switching.

The loader does not patch the Sollumz source. Keep the ordinary Sollumz add-on disabled while using a managed release. A detected active Sollumz instance is reported as a conflict rather than forcibly disabled.

## Tests

Run the loader's isolated standard-library tests with:

```powershell
py -3 -m unittest discover -s resollumz_loader/tests -v
```

The tests exercise catalog parsing, safe ZIP handling, installation and dependency isolation across three package layouts, including a legacy release without `dependencies.py`. Registration was smoke-tested in Blender 5.2.2 against the official `v2.7.2`, `v2.8.0` and `v2.9.0` packages. Blender 4.2+ remains the declared target; the minimum version and the visual installation/network flow still need manual validation.
