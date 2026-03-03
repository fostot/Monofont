# Monofont

A self-contained monospace bitmap font renderer for Terraria. Embeds the [Spleen 8x16](https://github.com/fcambus/spleen) bitmap font (994 Unicode glyphs) directly in code, builds a texture atlas at runtime, and draws text character-by-character via `SpriteBatch.Draw()`.

Zero compile-time dependencies on Terraria or XNA — everything is resolved at runtime through reflection.

## Features

- **Pixel-perfect monospace text** — every character is exactly 8x16 pixels
- **994 Unicode glyphs** — Latin, Latin Extended, Greek, Cyrillic, Box Drawing, Block Elements, Braille, Powerline, and common symbols
- **Zero dependencies** — no references to Terraria, XNA, or FNA assemblies at compile time
- **Self-contained** — the entire font is embedded as byte data; no external texture files needed
- **Runtime reflection** — automatically finds `Terraria.Main`, `SpriteBatch`, and XNA types from loaded assemblies
- **Lazy initialization** — safe to call `Initialize()` before the game is fully loaded; retries automatically

## Installation

### As a library reference

1. Download `Monofont.dll` from the [Releases](https://github.com/fostot/Monofont/releases) page
2. Place it alongside your mod's DLL or in a location where your mod loader can find it
3. Add a reference to `Monofont.dll` in your project

### Terraria directory placement

If your mod loader or injector loads assemblies from Terraria's install directory:

```
Steam:
  C:\Program Files (x86)\Steam\steamapps\common\Terraria\Monofont.dll

GOG:
  C:\Program Files\Terraria\Monofont.dll
```

Place `Monofont.dll` in the same folder as `Terraria.exe`.

### As a project reference

Add `Monofont.csproj` directly to your solution:

```xml
<ProjectReference Include="..\Monofont\Monofont.csproj" />
```

## Usage

```csharp
using Monofont;

// Initialize (call once, or repeatedly — it's idempotent)
// Returns false if the game isn't ready yet, true on success
MonoFont.Initialize();

// Draw text during a SpriteBatch pass
if (MonoFont.IsReady)
{
    // White text at (100, 50)
    MonoFont.DrawText("Hello, Terraria!", 100, 50, 255, 255, 255);

    // Colored text with alpha
    MonoFont.DrawText("Debug overlay", 100, 70, 0, 255, 0, 200);

    // Using Color4
    var color = new Color4(255, 200, 50);
    MonoFont.DrawText("Gold text", 100, 90, color);
}
```

## API Reference

### `MonoFont`

| Member | Description |
|---|---|
| `bool IsReady` | `true` when the atlas is built and rendering is available |
| `bool Initialize()` | Build the texture atlas and cache reflection handles. Safe to call repeatedly. Returns `true` on success, `false` if the game isn't ready yet or initialization failed permanently. |
| `void DrawText(string text, int x, int y, byte r, byte g, byte b, byte a = 255)` | Draw text at pixel coordinates with RGBA color. Characters not in the font render as `?`. |
| `void DrawText(string text, int x, int y, Color4 c)` | Draw text using a `Color4` value. |
| `int MeasureText(string text)` | Returns `text.Length * 8`. Always exact for monospace. |
| `int MeasureText(int charCount)` | Returns `charCount * 8`. Allocation-free overload. |
| `int CharsPerWidth(int pixelWidth)` | Number of characters that fit in the given pixel width. |

### `Color4`

Simple RGBA color struct.

| Member | Description |
|---|---|
| `Color4(byte r, byte g, byte b, byte a = 255)` | Constructor |
| `Color4 WithAlpha(byte a)` | Returns a copy with a different alpha value |

### Constants

| Constant | Value |
|---|---|
| `GlyphWidth` | 8 |
| `GlyphHeight` | 16 |

## Unicode Coverage

| Block | Range | Count |
|---|---|---|
| Basic Latin | U+0020–U+007E | 95 |
| Latin-1 Supplement | U+00A0–U+00FF | 96 |
| Latin Extended-A | U+0100–U+017F | 128 |
| Latin Extended-B | selected | ~20 |
| Greek | selected | ~30 |
| Cyrillic | U+0400–U+045F | 96 |
| Box Drawing | U+2500–U+257F | 128 |
| Block Elements | U+2580–U+259F | 32 |
| Braille Patterns | U+2800–U+28FF | 256 |
| Powerline | U+E0A0–U+E0B3 | ~10 |
| Misc Symbols | various | ~100 |

Unmapped characters fall back to `?`.

## Building from Source

Requires .NET Framework 4.8 SDK.

```bash
dotnet build Monofont.csproj -c Release
```

Output: `bin/Monofont.dll`

### Regenerating font data

The embedded glyph data is generated from the included BDF font file:

```bash
python gen_monofont.py
```

This parses `spleen-8x16.bdf` and outputs the `Encodings[]` and `GlyphData[]` arrays used by `MonoFont.cs`.

## How It Works

1. **Code generation** — `gen_monofont.py` parses the Spleen 8x16 BDF font and emits sorted Unicode code points (`Encodings[]`) and 1-bit-per-pixel bitmap rows (`GlyphData[]`, 16 bytes per glyph)

2. **Initialization** — `Initialize()` uses `AppDomain.CurrentDomain.GetAssemblies()` to find Terraria and XNA types via reflection. It creates a 320x576 `Texture2D` atlas, rasterizes all 994 glyphs into a pixel buffer (white for "on", transparent for "off"), and uploads to the GPU

3. **Rendering** — `DrawText()` binary-searches `Encodings[]` for each character, computes source/destination rectangles in the atlas grid (32 columns, 1px padding per cell), and calls `SpriteBatch.Draw()` via cached `MethodInfo`. The atlas stores white pixels; XNA's color parameter tints them to the requested color

## License

Monofont source code is provided as-is.

The embedded font data is from [Spleen](https://github.com/fcambus/spleen) by Frederic Cambus, licensed under the [BSD 2-Clause License](https://opensource.org/licenses/BSD-2-Clause).
