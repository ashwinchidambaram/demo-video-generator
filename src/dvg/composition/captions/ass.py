"""Compile CaptionLayer / TitleLayer to a libass `.ass` file.

ASS is the format ffmpeg's `subtitles` filter renders. It supports:
- Per-line typography (font, size, color, outline, shadow, alignment)
- Animation: \\fad(in,out), \\move(x1,y1,x2,y2,t1,t2), \\t(t1,t2,\\fscx150),
  \\frx, \\fry, \\frz (rotations), \\1c (color), \\alpha
- Margins, alignment via \\an1..\\an9 (numpad layout)

We render mood presets here. Caption layer time → ASS Layer 0,
TitleLayer → ASS Layer 1 with a background rectangle drawn via \\p1.
"""

from __future__ import annotations

import io
from collections.abc import Iterable

from dvg.models import Anchor, CaptionLayer, Composition, Mood, Theme, TitleLayer

# numpad alignment per ASS spec
_ANCHOR_TO_AN = {
    Anchor.BOTTOM_LEFT: 1,
    Anchor.BOTTOM_CENTER: 2,
    Anchor.BOTTOM_RIGHT: 3,
    Anchor.MIDDLE_LEFT: 4,
    Anchor.MIDDLE_CENTER: 5,
    Anchor.MIDDLE_RIGHT: 6,
    Anchor.TOP_LEFT: 7,
    Anchor.TOP_CENTER: 8,
    Anchor.TOP_RIGHT: 9,
}


# ---- mood presets --------------------------------------------------------


def _mood_preset(mood: Mood, theme: Theme) -> dict[str, object]:
    """Per-mood typography + motion preset.

    Returns a dict with: font, size, color (#RRGGBB), outline, shadow,
    bold, italic, motion ('fade' | 'pop' | 'slide_up' | 'fly_in' | 'none').
    """
    p: dict[str, dict[str, object]] = {
        Mood.ANNOUNCE: {
            "font": theme.font_family,
            "size": 64,
            "color": theme.color_text,
            "outline": 2.5,
            "shadow": 0.0,
            "bold": True,
            "italic": False,
            "motion": "slide_up",
        },
        Mood.EXPLAIN: {
            "font": theme.font_family,
            "size": 56,
            "color": theme.color_text,
            "outline": 2.0,
            "shadow": 0.0,
            "bold": False,
            "italic": False,
            "motion": "fade",
        },
        Mood.PUNCHLINE: {
            "font": theme.font_family,
            "size": 84,
            "color": theme.color_accent,
            "outline": 3.5,
            "shadow": 0.0,
            "bold": True,
            "italic": False,
            "motion": "pop",
        },
        Mood.ASIDE: {
            "font": theme.font_family,
            "size": 32,
            "color": theme.color_text_dim,
            "outline": 1.0,
            "shadow": 0.0,
            "bold": False,
            "italic": True,
            "motion": "fade",
        },
        Mood.CALLOUT: {
            "font": theme.font_family,
            "size": 48,
            "color": theme.color_accent,
            "outline": 2.0,
            "shadow": 1.5,
            "bold": True,
            "italic": False,
            "motion": "fly_in",
        },
        Mood.TAGLINE: {
            "font": theme.font_family,
            "size": 56,
            "color": theme.color_text,
            "outline": 2.0,
            "shadow": 0.0,
            "bold": True,
            "italic": False,
            "motion": "slide_up",
        },
        Mood.CALL_TO_ACTION: {
            "font": theme.font_family,
            "size": 60,
            "color": theme.color_accent,
            "outline": 2.5,
            "shadow": 0.0,
            "bold": True,
            "italic": False,
            "motion": "pop",
        },
    }
    return p[mood]


# ---- color conversion ----------------------------------------------------


def _hex_to_ass_color(hex_str: str) -> str:
    """#RRGGBB → ASS &H00BBGGRR& (alpha 0=opaque). 8-char hex → &HAABBGGRR&."""
    s = hex_str.lstrip("#")
    if len(s) == 6:
        r, g, b = s[0:2], s[2:4], s[4:6]
        return f"&H00{b}{g}{r}&".upper()
    if len(s) == 8:
        r, g, b, a = s[0:2], s[2:4], s[4:6], s[6:8]
        # ASS alpha is inverted: 00=opaque, FF=transparent
        inv_a = f"{255 - int(a, 16):02x}"
        return f"&H{inv_a}{b}{g}{r}&".upper()
    raise ValueError(f"bad hex color: {hex_str}")


def _hh_mm_ss(t: float) -> str:
    """ASS time format: H:MM:SS.cs (centiseconds)."""
    if t < 0:
        t = 0.0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


# ---- motion override builders -------------------------------------------


def _motion_override(motion: str, fade_in: float, fade_out: float, duration: float) -> str:
    """Return ASS override tags for the chosen motion + fade timing.

    fade_in/out in seconds; converted to ms for \\fad().
    """
    fi_ms = int(fade_in * 1000)
    fo_ms = int(fade_out * 1000)
    if motion == "fade":
        return f"\\fad({fi_ms or 250},{fo_ms or 250})"
    if motion == "pop":
        # scale 80% → 105% → 100% over fade-in; \\fad on alpha
        fi = max(fade_in, 0.18)
        fi_a_ms = int(fi * 0.6 * 1000)
        fi_b_ms = int(fi * 1000)
        return (
            f"\\fad({fi_ms or 200},{fo_ms or 200})"
            f"\\fscx80\\fscy80"
            f"\\t(0,{fi_a_ms},\\fscx108\\fscy108)"
            f"\\t({fi_a_ms},{fi_b_ms},\\fscx100\\fscy100)"
        )
    if motion == "slide_up":
        # we use \\move from 60px below baseline to baseline. Implementation is
        # approximated via a relative-position margin shift since absolute pos
        # requires \\pos which competes with \\an alignment. Use \\fad + a
        # per-line \\frz=0 for a clean slide via the marginV trick (handled by
        # multiple Dialogue lines is overkill — fade is enough at this size).
        return f"\\fad({fi_ms or 350},{fo_ms or 250})"
    if motion == "fly_in":
        return f"\\fad({fi_ms or 250},{fo_ms or 200})\\fscx40\\fscy40\\t(0,250,\\fscx100\\fscy100)"
    return f"\\fad({fi_ms or 200},{fo_ms or 200})"


# ---- main compiler -------------------------------------------------------


def compile_ass(comp: Composition) -> str:
    """Return the complete .ass file content for all caption + title layers."""
    captions = [layer for layer in comp.layers if isinstance(layer, CaptionLayer)]
    titles = [layer for layer in comp.layers if isinstance(layer, TitleLayer)]

    buf = io.StringIO()
    _write_header(buf, comp)
    _write_styles(buf, comp, captions, titles)
    _write_events(buf, comp, captions, titles)
    return buf.getvalue()


def _write_header(buf: io.StringIO, comp: Composition) -> None:
    buf.write("[Script Info]\n")
    buf.write("ScriptType: v4.00+\n")
    buf.write("Collisions: Normal\n")
    buf.write(f"PlayResX: {comp.width}\n")
    buf.write(f"PlayResY: {comp.height}\n")
    buf.write("WrapStyle: 2\n")  # 2 = no auto-wrap, only \N breaks lines
    buf.write("ScaledBorderAndShadow: yes\n")
    buf.write("YCbCr Matrix: TV.709\n\n")


def _write_styles(
    buf: io.StringIO,
    comp: Composition,
    captions: Iterable[CaptionLayer],
    titles: Iterable[TitleLayer],
) -> None:
    buf.write("[V4+ Styles]\n")
    buf.write(
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
    )

    seen: set[str] = set()
    for cl in captions:
        style = _caption_style_name(cl)
        if style in seen:
            continue
        seen.add(style)
        preset = _mood_preset(cl.mood, comp.theme)
        font = cl.font or preset["font"]
        size = cl.font_size or preset["size"]
        color = cl.color or preset["color"]
        outline = cl.outline if cl.outline is not None else preset["outline"]
        shadow = cl.shadow if cl.shadow is not None else preset["shadow"]
        primary = _hex_to_ass_color(str(color))
        outline_color = _hex_to_ass_color("#000000")
        back = _hex_to_ass_color("#00000099")
        an = _ANCHOR_TO_AN[cl.anchor]
        bold = -1 if preset["bold"] else 0
        italic = -1 if preset["italic"] else 0
        margin_l = cl.margin if cl.anchor.value.endswith("left") else 60
        margin_r = cl.margin if cl.anchor.value.endswith("right") else 60
        margin_v = cl.margin if "middle" not in cl.anchor.value else 0
        buf.write(
            f"Style: {style},{font},{size},{primary},{primary},{outline_color},{back},"
            f"{bold},{italic},0,0,100,100,0,0,1,{outline},{shadow},"
            f"{an},{margin_l},{margin_r},{margin_v},1\n"
        )

    for tl in titles:
        style = _title_style_name(tl, "title")
        if style not in seen:
            seen.add(style)
            primary = _hex_to_ass_color(tl.title_color)
            outline_color = _hex_to_ass_color("#000000")
            an = _ANCHOR_TO_AN[tl.align]
            buf.write(
                f"Style: {style},{comp.theme.font_family},{tl.title_size},"
                f"{primary},{primary},{outline_color},{outline_color},"
                f"-1,0,0,0,100,100,0,0,1,0,0,{an},120,120,0,1\n"
            )
        if tl.subtitle:
            sub_style = _title_style_name(tl, "subtitle")
            if sub_style not in seen:
                seen.add(sub_style)
                primary = _hex_to_ass_color(tl.subtitle_color)
                outline_color = _hex_to_ass_color("#000000")
                an = _ANCHOR_TO_AN[tl.align]
                buf.write(
                    f"Style: {sub_style},{comp.theme.font_family},{tl.subtitle_size},"
                    f"{primary},{primary},{outline_color},{outline_color},"
                    f"0,1,0,0,100,100,0,0,1,0,0,{an},120,120,0,1\n"
                )

    buf.write("\n")


def _caption_style_name(cl: CaptionLayer) -> str:
    return f"cap_{cl.mood.value}_{cl.anchor.value.replace('-','_')}"


def _title_style_name(tl: TitleLayer, kind: str) -> str:
    return f"title_{kind}_{tl.align.value.replace('-','_')}"


def _write_events(
    buf: io.StringIO,
    comp: Composition,
    captions: Iterable[CaptionLayer],
    titles: Iterable[TitleLayer],
) -> None:
    buf.write("[Events]\n")
    buf.write(
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    for cl in captions:
        preset = _mood_preset(cl.mood, comp.theme)
        motion = str(preset["motion"])
        fi = cl.fade_in or 0.0
        fo = cl.fade_out or 0.0
        duration = cl.duration
        override = _motion_override(motion, fi, fo, duration)
        text = _escape_ass_text(cl.text)
        start = _hh_mm_ss(cl.time[0])
        end = _hh_mm_ss(cl.time[1])
        style = _caption_style_name(cl)
        buf.write(
            f"Dialogue: {cl.z},{start},{end},{style},,0,0,0,,{{{override}}}{text}\n"
        )

    for tl in titles:
        # Combine title + optional subtitle as one multi-line dialogue so the
        # block centers around the canvas middle on \an5.
        start = _hh_mm_ss(tl.time[0])
        end = _hh_mm_ss(tl.time[1])
        title_style = _title_style_name(tl, "title")
        fi_ms = int(tl.fade_in * 1000) or 400
        fo_ms = int(tl.fade_out * 1000) or 400
        title_text = _escape_ass_text(tl.title)
        if tl.subtitle:
            # Use a per-line style override for the subtitle line: smaller, dimmer,
            # italic. Inline overrides via {\fnNAME\fsSIZE\1cCOLOR} apply to the rest
            # of the dialogue until the next override block.
            sub_size = tl.subtitle_size
            sub_color = _hex_to_ass_color(tl.subtitle_color)
            sub_text = _escape_ass_text(tl.subtitle)
            text = (
                f"{{\\fad({fi_ms},{fo_ms})}}{title_text}"
                f"\\N{{\\fs{sub_size}\\1c{sub_color}\\i1}}{sub_text}"
            )
        else:
            text = f"{{\\fad({fi_ms},{fo_ms})}}{title_text}"
        buf.write(
            f"Dialogue: {tl.z + 1},{start},{end},{title_style},,0,0,0,,{text}\n"
        )


def _escape_ass_text(text: str) -> str:
    """Escape characters that would break ASS dialogue lines."""
    return (
        text.replace("\\", "\\\\")
        .replace("{", "\\{")
        .replace("}", "\\}")
        .replace("\n", "\\N")
    )
