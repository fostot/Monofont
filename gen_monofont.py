#!/usr/bin/env python3
"""Generate MonoFont.cs from Spleen 8x16 BDF file."""

# Parse BDF
with open('A:/3P/Terraria/terraria-modder/spleen-8x16.bdf', 'r', encoding='utf-8') as f:
    content = f.read()

chars = {}
blocks = content.split('STARTCHAR ')
for block in blocks[1:]:
    lines = block.strip().split('\n')
    encoding = None
    bitmap_data = []
    in_bitmap = False
    for line in lines:
        line = line.strip()
        if line.startswith('ENCODING '):
            encoding = int(line.split()[1])
        elif line == 'BITMAP':
            in_bitmap = True
        elif line == 'ENDCHAR':
            in_bitmap = False
        elif in_bitmap:
            bitmap_data.append(int(line, 16))
    if encoding is not None and encoding >= 0:
        while len(bitmap_data) < 16:
            bitmap_data.append(0)
        chars[encoding] = bitmap_data[:16]

sorted_encodings = sorted(chars.keys())
total = len(sorted_encodings)

# Build encoding table lines
enc_lines = []
line_items = []
for i, enc in enumerate(sorted_encodings):
    line_items.append(f'0x{enc:04X}')
    if len(line_items) == 16 or i == total - 1:
        enc_lines.append('            ' + ', '.join(line_items) + ',')
        line_items = []

# Build glyph data lines
glyph_lines = []
for enc in sorted_encodings:
    data = chars[enc]
    hex_vals = ', '.join(f'0x{b:02X}' for b in data)
    glyph_lines.append(f'            {hex_vals}, // U+{enc:04X}')

# Find the index of '?' in sorted encodings for fallback
question_idx = sorted_encodings.index(0x3F)

# Write MonoFont.cs
out_path = 'A:/3P/Terraria/terraria-modder/src/Core/UI/MonoFont.cs'
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(f"""// Spleen 8x16 monospace bitmap font renderer
// Font: Spleen 8x16 2.2.0 by Frederic Cambus
// License: BSD 2-Clause (https://github.com/fcambus/spleen)

using System;
using System.Linq;
using System.Reflection;
using TerrariaModder.Core.Logging;

namespace TerrariaModder.Core.UI
{{
    /// <summary>
    /// Monospace bitmap font (Spleen 8x16) for pixel-perfect log text rendering.
    /// Creates a texture atlas at runtime from embedded glyph data, draws via SpriteBatch.
    /// MeasureText is always exact: text.Length * GlyphWidth.
    /// Supports {total} Unicode characters including Latin, Greek, Cyrillic, box drawing, etc.
    /// </summary>
    internal static class MonoFont
    {{
        private static readonly ILog _log = LogManager.GetLogger("MonoFont");

        public const int GlyphWidth = 8;
        public const int GlyphHeight = 16;
        private const int TotalGlyphs = {total};
        private const int AtlasWidth = TotalGlyphs * GlyphWidth; // {total * 8}
        private const int AtlasHeight = GlyphHeight; // 16
        private const int FallbackGlyph = {question_idx}; // '?' glyph index

        // -- State ------------------------------------------------

        private static object _atlas;       // Texture2D
        private static bool _initialized;
        private static bool _initFailed;

        // -- Reflection cache -------------------------------------

        private static object _spriteBatch;
        private static MethodInfo _drawMethod;      // Draw(Texture2D, Rectangle dest, Rectangle? source, Color)
        private static ConstructorInfo _rectCtor;    // Rectangle(int, int, int, int)
        private static ConstructorInfo _colorCtor;   // Color(int r, int g, int b, int a)
        private static Type _rectType;
        private static Type _nullableRectType;

        // -- Encoding lookup (sorted for binary search) -----------

        private static readonly ushort[] Encodings = new ushort[]
        {{
""")
    for line in enc_lines:
        f.write(line + '\n')
    f.write(f"""        }};

        // -- Glyph bitmap data (16 bytes per glyph, MSB = left) ---
        // {total} glyphs x 16 bytes = {total * 16} bytes

        private static readonly byte[] GlyphData = new byte[]
        {{
""")
    for line in glyph_lines:
        f.write(line + '\n')
    f.write("""        };

        // -- Public API -------------------------------------------

        /// <summary>
        /// Whether the font atlas is ready for rendering.
        /// </summary>
        public static bool IsReady => _initialized && !_initFailed;

        /// <summary>
        /// Initialize the font atlas and reflection cache.
        /// Safe to call repeatedly -- returns cached result after first success/failure.
        /// </summary>
        public static bool Initialize()
        {
            if (_initialized) return !_initFailed;
            if (_initFailed) return false;

            try
            {
                // -- Find XNA types --------------------------
                var mainType = typeof(Terraria.Main);
                Type texture2dType = null;
                Type spriteBatchType = null;

                foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (texture2dType == null)
                        texture2dType = asm.GetType("Microsoft.Xna.Framework.Graphics.Texture2D");
                    if (spriteBatchType == null)
                        spriteBatchType = asm.GetType("Microsoft.Xna.Framework.Graphics.SpriteBatch");
                    _rectType = _rectType ?? asm.GetType("Microsoft.Xna.Framework.Rectangle");
                    var colorType = asm.GetType("Microsoft.Xna.Framework.Color");
                    if (colorType != null && _colorCtor == null)
                        _colorCtor = colorType.GetConstructor(new[] { typeof(int), typeof(int), typeof(int), typeof(int) });

                    if (texture2dType != null && spriteBatchType != null && _rectType != null && _colorCtor != null)
                        break;
                }

                if (texture2dType == null || spriteBatchType == null || _rectType == null || _colorCtor == null)
                {
                    _log?.Error("[MonoFont] Failed to find XNA types");
                    _initFailed = true;
                    return false;
                }

                _rectCtor = _rectType.GetConstructor(new[] { typeof(int), typeof(int), typeof(int), typeof(int) });
                _nullableRectType = typeof(Nullable<>).MakeGenericType(_rectType);

                // -- Get SpriteBatch -------------------------
                var sbField = mainType.GetField("spriteBatch", BindingFlags.Public | BindingFlags.Static);
                _spriteBatch = sbField?.GetValue(null);
                if (_spriteBatch == null)
                {
                    _log?.Warn("[MonoFont] SpriteBatch not available yet");
                    return false; // Don't mark as failed -- retry later
                }

                // -- Get GraphicsDevice ----------------------
                object graphicsDevice = null;
                var graphicsField = mainType.GetField("graphics", BindingFlags.Public | BindingFlags.Static);
                if (graphicsField != null)
                {
                    var gm = graphicsField.GetValue(null);
                    if (gm != null)
                    {
                        var gdProp = gm.GetType().GetProperty("GraphicsDevice");
                        graphicsDevice = gdProp?.GetValue(gm);
                    }
                }
                if (graphicsDevice == null)
                {
                    var instField = mainType.GetField("instance", BindingFlags.Public | BindingFlags.Static);
                    var inst = instField?.GetValue(null);
                    if (inst != null)
                    {
                        var gdProp = inst.GetType().GetProperty("GraphicsDevice");
                        graphicsDevice = gdProp?.GetValue(inst);
                    }
                }
                if (graphicsDevice == null)
                {
                    _log?.Warn("[MonoFont] GraphicsDevice not available yet");
                    return false;
                }

                // -- Find Draw(Texture2D, Rectangle, Rectangle?, Color) --
                _drawMethod = spriteBatchType.GetMethods()
                    .FirstOrDefault(m =>
                        m.Name == "Draw" &&
                        m.GetParameters().Length == 4 &&
                        m.GetParameters()[0].ParameterType == texture2dType &&
                        m.GetParameters()[1].ParameterType == _rectType);

                if (_drawMethod == null)
                {
                    _log?.Error("[MonoFont] Could not find Draw(Texture2D, Rectangle, Rectangle?, Color)");
                    _initFailed = true;
                    return false;
                }

                // -- Build atlas texture ---------------------
                var gdType = graphicsDevice.GetType();
                var tex2dCtor = texture2dType.GetConstructors()
                    .FirstOrDefault(c =>
                    {
                        var p = c.GetParameters();
                        return p.Length == 3 &&
                               p[1].ParameterType == typeof(int) &&
                               p[2].ParameterType == typeof(int) &&
                               p[0].ParameterType.IsAssignableFrom(gdType);
                    });

                if (tex2dCtor == null)
                {
                    _log?.Error("[MonoFont] Could not find Texture2D(GraphicsDevice, int, int) constructor");
                    _initFailed = true;
                    return false;
                }

                _atlas = tex2dCtor.Invoke(new object[] { graphicsDevice, AtlasWidth, AtlasHeight });

                // -- Fill pixel data -------------------------
                // White (0xFFFFFFFF) for "on", transparent (0x00000000) for "off"
                var pixels = new uint[AtlasWidth * AtlasHeight];

                for (int glyphIdx = 0; glyphIdx < TotalGlyphs; glyphIdx++)
                {
                    int dataOffset = glyphIdx * GlyphHeight;
                    int atlasX = glyphIdx * GlyphWidth;

                    for (int row = 0; row < GlyphHeight; row++)
                    {
                        byte rowBits = GlyphData[dataOffset + row];
                        for (int bit = 0; bit < GlyphWidth; bit++)
                        {
                            if ((rowBits & (0x80 >> bit)) != 0)
                                pixels[row * AtlasWidth + atlasX + bit] = 0xFFFFFFFF;
                        }
                    }
                }

                // -- Upload to GPU ---------------------------
                var setDataMethod = texture2dType.GetMethods()
                    .FirstOrDefault(m =>
                        m.Name == "SetData" &&
                        m.IsGenericMethodDefinition &&
                        m.GetParameters().Length == 1);

                if (setDataMethod == null)
                {
                    _log?.Error("[MonoFont] Could not find SetData<T>(T[]) method");
                    _initFailed = true;
                    return false;
                }

                var setDataUint = setDataMethod.MakeGenericMethod(typeof(uint));
                setDataUint.Invoke(_atlas, new object[] { pixels });

                _initialized = true;
                _log?.Info($"[MonoFont] Spleen 8x16 atlas created ({AtlasWidth}x{AtlasHeight}, {TotalGlyphs} glyphs)");
                return true;
            }
            catch (Exception ex)
            {
                _log?.Error($"[MonoFont] Init failed: {ex.Message}");
                _initFailed = true;
                return false;
            }
        }

        /// <summary>
        /// Draw text at pixel coordinates using the monospace font.
        /// Characters not in the font render as '?'.
        /// </summary>
        public static void DrawText(string text, int x, int y, Color4 c)
        {
            DrawText(text, x, y, c.R, c.G, c.B, c.A);
        }

        /// <summary>
        /// Draw text at pixel coordinates using the monospace font.
        /// </summary>
        public static void DrawText(string text, int x, int y, byte r, byte g, byte b, byte a = 255)
        {
            if (!_initialized || _initFailed || string.IsNullOrEmpty(text)) return;

            var color = _colorCtor.Invoke(new object[] { (int)r, (int)g, (int)b, (int)a });

            for (int i = 0; i < text.Length; i++)
            {
                int ch = text[i];
                int glyphIdx = FindGlyph(ch);

                int srcX = glyphIdx * GlyphWidth;
                var srcRect = _rectCtor.Invoke(new object[] { srcX, 0, GlyphWidth, GlyphHeight });
                var nullableSrc = Activator.CreateInstance(_nullableRectType, srcRect);

                int destX = x + i * GlyphWidth;
                var destRect = _rectCtor.Invoke(new object[] { destX, y, GlyphWidth, GlyphHeight });

                _drawMethod.Invoke(_spriteBatch, new object[] { _atlas, destRect, nullableSrc, color });
            }
        }

        /// <summary>
        /// Measure text width in pixels. Always exact: length x 8.
        /// </summary>
        public static int MeasureText(string text)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            return text.Length * GlyphWidth;
        }

        /// <summary>
        /// Measure text width in pixels for a character count without allocating.
        /// </summary>
        public static int MeasureText(int charCount)
        {
            return charCount * GlyphWidth;
        }

        /// <summary>
        /// Number of characters that fit in the given pixel width.
        /// </summary>
        public static int CharsPerWidth(int pixelWidth)
        {
            return Math.Max(1, pixelWidth / GlyphWidth);
        }

        // -- Internals --------------------------------------------

        /// <summary>
        /// Binary search the Encodings table. Returns glyph index, or '?' glyph on miss.
        /// </summary>
        private static int FindGlyph(int codePoint)
        {
            if (codePoint > ushort.MaxValue) return FallbackGlyph;

            ushort cp = (ushort)codePoint;
            int lo = 0, hi = Encodings.Length - 1;
            while (lo <= hi)
            {
                int mid = lo + (hi - lo) / 2;
                ushort val = Encodings[mid];
                if (val == cp) return mid;
                if (val < cp) lo = mid + 1;
                else hi = mid - 1;
            }

            return FallbackGlyph;
        }
    }
}
""")

print(f'MonoFont.cs written with {total} glyphs ({total * 16} bytes glyph data)')
