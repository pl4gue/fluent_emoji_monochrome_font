from pathlib import Path
import re
import sys
import tempfile

from fontTools.fontBuilder import FontBuilder
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.svgLib.path import parse_path


SRC = Path("./fluent-emoji-webfont/build")
OUT = Path("dist/FluentEmojiHighContrastMonochrome.ttf")

UPM = 1024
MAX_ERR = 1.0

CELL_ADVANCE = 1275
SCALE = 37.5
X_OFFSET = 37.5
Y_OFFSET = 950.0


def parse_codepoints(path):
    match = re.search(r"_emoji_(.+)\.svg$", path.name)
    if not match:
        raise ValueError(f"Can't extract Unicode sequence from {path.name}")

    return tuple(
        int(part.removeprefix("u"), 16)
        for part in match.group(1).split("_")
    )


def glyph_name(codepoints):
    return "u" + "_".join(f"{cp:X}" for cp in codepoints)


def codepoint_glyph_name(cp):
    return glyph_name((cp,))


def svg_to_glyph(path):
    base_pen = TTGlyphPen(None)

    pen = Cu2QuPen(
        base_pen,
        max_err=MAX_ERR,
        reverse_direction=False,
    )

    transform = TransformPen(
        pen,
        (
            SCALE,
            0,
            0,
            -SCALE,
            X_OFFSET,
            Y_OFFSET,
        ),
    )

    text = path.read_text(encoding="utf-8")

    for d in re.findall(
        r'<path\b[^>]*\bd="([^"]+)"',
        text,
    ):
        parse_path(d, transform)

    return base_pen.glyph()


def empty_glyph():
    return TTGlyphPen(None).glyph()


def main():
    svg_files = sorted(SRC.glob("*.svg"))

    print(f"Found {len(svg_files)} SVG files")

    glyphs = {
        ".notdef": empty_glyph(),
    }

    cmap = {}
    metrics = {
        ".notdef": (UPM, 0),
    }

    sequences = []

    successful = 0
    failed = 0

    for index, path in enumerate(svg_files, 1):
        try:
            codepoints = parse_codepoints(path)
            name = glyph_name(codepoints)

            glyphs[name] = svg_to_glyph(path)
            metrics[name] = (CELL_ADVANCE, X_OFFSET)

            if len(codepoints) == 1:
                cmap[codepoints[0]] = name
            else:
                sequences.append(codepoints)

            successful += 1

        except Exception as exc:
            failed += 1
            print(
                f"\nERROR: {path.name}\n       {exc}",
                file=sys.stderr,
            )

        if index % 100 == 0 or index == len(svg_files):
            print(
                f"\r[{index:4}/{len(svg_files)}] "
                f"success={successful} failed={failed}",
                end="",
            )

    print()

    if failed:
        raise SystemExit(f"{failed} SVGs failed to convert")

    # ------------------------------------------------------------------
    # Add invisible glyphs for Unicode codepoints which only occur as
    # components of sequences.
    #
    # This is necessary because GSUB operates on glyphs, not raw Unicode
    # codepoints. ZWJ, skin-tone modifiers, and U+20E3 may not have their
    # own SVGs, but they still need glyph IDs for the substitution input.
    # ------------------------------------------------------------------

    sequence_codepoints = {
        cp
        for sequence in sequences
        for cp in sequence
    }

    missing_components = sorted(sequence_codepoints - set(cmap))

    for cp in missing_components:
        name = codepoint_glyph_name(cp)

        if name not in glyphs:
            glyphs[name] = empty_glyph()

        # Combining components / modifiers must not occupy a cell.
        metrics[name] = (0, 0)
        cmap[cp] = name

    print(f"Glyphs:          {len(glyphs) - 1}")
    print(f"Single codepoints: {successful - len(sequences)}")
    print(f"Sequences:       {len(sequences)}")
    print(f"GSUB components: {len(missing_components)}")

    # ------------------------------------------------------------------
    # Build font.
    # ------------------------------------------------------------------

    glyph_order = list(glyphs)

    fb = FontBuilder(UPM, isTTF=True)

    fb.setupGlyphOrder(glyph_order)
    fb.setupGlyf(glyphs)

    fb.setupHorizontalMetrics(metrics)

    fb.setupHorizontalHeader(
        ascent=950,
        descent=-250,
        lineGap=0,
    )

    fb.setupCharacterMap(cmap)

    fb.setupOS2(
        sTypoAscender=950,
        sTypoDescender=-250,
        sTypoLineGap=0,
        usWinAscent=950,
        usWinDescent=250,
    )

    fb.setupNameTable({
        "familyName": "Fluent Emoji HC Mono",
        "styleName": "Regular",
        "fullName": "Fluent Emoji HC Mono Regular",
        "psName": "FluentEmojiHCMono-Regular",
    })

    fb.setupPost()
    fb.setupMaxp()

    # ------------------------------------------------------------------
    # GSUB
    #
    # Each multi-codepoint SVG corresponds to one ligature glyph.
    #
    # Example:
    #
    #   u1F469 u200D u1F4BB
    #
    # becomes:
    #
    #   u1F469_200D_1F4BB
    #
    # ------------------------------------------------------------------

    feature_lines = [
        "languagesystem DFLT dflt;",
        "",
        "feature liga {",
    ]

    # Longest sequences first. This is useful for sequences which share
    # prefixes, e.g. a 4-codepoint sequence and a 6-codepoint extension.
    for sequence in sorted(
        sequences,
        key=lambda seq: (-len(seq), seq),
    ):
        input_glyphs = " ".join(
            codepoint_glyph_name(cp)
            for cp in sequence
        )

        output_glyph = glyph_name(sequence)

        feature_lines.append(
            f"    sub {input_glyphs} by {output_glyph};"
        )

    feature_lines.append("} liga;")
    feature_text = "\n".join(feature_lines) + "\n"

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".fea",
        encoding="utf-8",
        delete=False,
    ) as feature_file:
        feature_file.write(feature_text)
        feature_path = feature_file.name

    try:
        addOpenTypeFeatures(
            fb.font,
            feature_path,
        )
    finally:
        Path(feature_path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Save.
    # ------------------------------------------------------------------

    fb.save(OUT)

    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
