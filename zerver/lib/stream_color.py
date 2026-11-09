import colorsys
import math
from dataclasses import dataclass

STREAM_ASSIGNMENT_COLORS = [
    "#76ce90",
    "#fae589",
    "#a6c7e5",
    "#e79ab5",
    "#bfd56f",
    "#f4ae55",
    "#b0a5fd",
    "#addfe5",
    "#f5ce6e",
    "#c2726a",
    "#94c849",
    "#bd86e5",
    "#ee7e4a",
    "#a6dcbf",
    "#95a5fd",
    "#53a063",
    "#9987e1",
    "#e4523d",
    "#c2c2c2",
    "#4f8de4",
    "#c6a8ad",
    "#e7cc4d",
    "#c8bebf",
    "#a47462",
]


def pick_colors(
    used_colors: set[str], color_map: dict[int, str], recipient_ids: list[int]
) -> dict[int, str]:
    used_colors = set(used_colors)
    recipient_ids = sorted(recipient_ids)
    result = {}

    other_recipient_ids = []
    for recipient_id in recipient_ids:
        if recipient_id in color_map:
            color = color_map[recipient_id]
            result[recipient_id] = color
            used_colors.add(color)
        else:
            other_recipient_ids.append(recipient_id)

    available_colors = [s for s in STREAM_ASSIGNMENT_COLORS if s not in used_colors]

    for i, recipient_id in enumerate(other_recipient_ids):
        if i < len(available_colors):
            color = available_colors[i]
        else:
            # We have to start reusing old colors, and we use recipient_id
            # to choose the color.
            color = STREAM_ASSIGNMENT_COLORS[recipient_id % len(STREAM_ASSIGNMENT_COLORS)]
        result[recipient_id] = color

    return result


# Recipient bar colors, ported from web/src/stream_color.ts for use in
# emails, which can't run that JavaScript. The arithmetic mirrors the
# colord library (including its rounding), so a channel's recipient bar
# in an email matches the web app's exactly; keep the two in sync.

# CIE Lab reference white (D50), as used by colord.
WHITE_X = 96.422
WHITE_Y = 100.0
WHITE_Z = 82.521
EPSILON = 216 / 24389
KAPPA = 24389 / 27


@dataclass
class RGB:
    r: float
    g: float
    b: float


@dataclass
class Lab:
    l: float  # noqa: E741
    a: float
    b: float


def _js_round(value: float, digits: int = 0) -> float:
    # JavaScript's Math.round rounds halves up, unlike Python's round().
    factor = 10**digits
    return math.floor(value * factor + 0.5) / factor


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _srgb_to_linear(channel: float) -> float:
    c = channel / 255
    return c / 12.92 if c < 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _linear_to_srgb(channel: float) -> float:
    return 255 * (1.055 * channel ** (1 / 2.4) - 0.055 if channel > 0.0031308 else 12.92 * channel)


def _rgb_to_lab(rgb: RGB) -> Lab:
    r = _srgb_to_linear(rgb.r)
    g = _srgb_to_linear(rgb.g)
    b = _srgb_to_linear(rgb.b)
    # sRGB to XYZ (D65), then Bradford-adapted to D50.
    x65 = 100 * (0.4124564 * r + 0.3575761 * g + 0.1804375 * b)
    y65 = 100 * (0.2126729 * r + 0.7151522 * g + 0.072175 * b)
    z65 = 100 * (0.0193339 * r + 0.119192 * g + 0.9503041 * b)
    x = _clamp(1.0478112 * x65 + 0.0228866 * y65 - 0.050127 * z65, 0, WHITE_X)
    y = _clamp(0.0295424 * x65 + 0.9904844 * y65 - 0.0170491 * z65, 0, WHITE_Y)
    z = _clamp(-0.0092345 * x65 + 0.0150436 * y65 + 0.7521316 * z65, 0, WHITE_Z)

    def f(t: float) -> float:
        return t ** (1 / 3) if t > EPSILON else (KAPPA * t + 16) / 116

    fx, fy, fz = f(x / WHITE_X), f(y / WHITE_Y), f(z / WHITE_Z)
    return Lab(l=116 * fy - 16, a=500 * (fx - fy), b=200 * (fy - fz))


def _lab_to_rgb(lab: Lab) -> RGB:
    fy = (lab.l + 16) / 116
    fx = lab.a / 500 + fy
    fz = fy - lab.b / 200
    x = (fx**3 if fx**3 > EPSILON else (116 * fx - 16) / KAPPA) * WHITE_X
    y = (fy**3 if lab.l > 8 else lab.l / KAPPA) * WHITE_Y
    z = (fz**3 if fz**3 > EPSILON else (116 * fz - 16) / KAPPA) * WHITE_Z
    # Bradford-adapt D50 back to D65, then XYZ to linear sRGB.
    x65 = 0.9555766 * x - 0.0230393 * y + 0.0631636 * z
    y65 = -0.0282895 * x + 1.0099416 * y + 0.0210077 * z
    z65 = 0.0122982 * x - 0.020483 * y + 1.3299098 * z
    return RGB(
        r=_clamp(
            _linear_to_srgb(0.032404542 * x65 - 0.015371385 * y65 - 0.004985314 * z65), 0, 255
        ),
        g=_clamp(_linear_to_srgb(-0.00969266 * x65 + 0.018760108 * y65 + 0.00041556 * z65), 0, 255),
        b=_clamp(
            _linear_to_srgb(0.000556434 * x65 - 0.002040259 * y65 + 0.010572252 * z65), 0, 255
        ),
    )


def _parse_hex(hex_color: str) -> RGB:
    # Subscription colors are validated by check_color, which also
    # accepts 3- to 5-digit codes. Like colord, ignore the alpha digit
    # of a 4-digit code, and treat an unparseable 5-digit one as black.
    hex_digits = hex_color.removeprefix("#")
    if len(hex_digits) in (3, 4):
        hex_digits = "".join(digit * 2 for digit in hex_digits[:3])
    elif len(hex_digits) != 6:
        hex_digits = "000000"
    return RGB(r=int(hex_digits[0:2], 16), g=int(hex_digits[2:4], 16), b=int(hex_digits[4:6], 16))


def _to_hex(rgb: RGB) -> str:
    return "#" + "".join(f"{int(_js_round(channel)):02x}" for channel in (rgb.r, rgb.g, rgb.b))


def get_corrected_color(hex_color: str) -> RGB:
    # Restricts the LCH lightness of a color to between 20 and 75.
    lab = _rgb_to_lab(_parse_hex(hex_color))
    a = _js_round(lab.a, 3)
    b = _js_round(lab.b, 3)
    hue = math.degrees(math.atan2(b, a))
    lightness = _clamp(_js_round(lab.l, 2), 20, 75)
    chroma = _js_round(math.sqrt(a * a + b * b), 2)
    hue = _js_round(hue + 360 if hue < 0 else hue, 2) % 360
    return _lab_to_rgb(
        Lab(
            l=lightness,
            a=chroma * math.cos(math.radians(hue)),
            b=chroma * math.sin(math.radians(hue)),
        )
    )


def _mix(base_hex: str, color_hex: str, ratio: float) -> str:
    base = _rgb_to_lab(_parse_hex(base_hex))
    color = _rgb_to_lab(_parse_hex(color_hex))
    return _to_hex(
        _lab_to_rgb(
            Lab(
                l=_clamp(base.l + (color.l - base.l) * ratio, 0, 400),
                a=base.a + (color.a - base.a) * ratio,
                b=base.b + (color.b - base.b) * ratio,
            )
        )
    )


@dataclass
class StreamColors:
    recipient_bar_color: str
    recipient_bar_color_dark: str
    privacy_icon_color: str
    privacy_icon_color_dark: str


def get_stream_colors(hex_color: str) -> StreamColors:
    corrected_color = get_corrected_color(hex_color)
    corrected_hex = _to_hex(corrected_color)
    hue, lightness, saturation = colorsys.rgb_to_hls(
        corrected_color.r / 255, corrected_color.g / 255, corrected_color.b / 255
    )
    r, g, b = colorsys.hls_to_rgb(hue, _clamp(lightness - 0.12, 0, 1), saturation)
    darkened_color = RGB(r=255 * r, g=255 * g, b=255 * b)
    return StreamColors(
        # Matches get_recipient_bar_color in web/src/stream_color.ts.
        recipient_bar_color=_mix("#f9f9f9", corrected_hex, 0.22),
        recipient_bar_color_dark=_mix("#000000", corrected_hex, 0.38),
        # Matches get_stream_privacy_icon_color in web/src/stream_color.ts.
        privacy_icon_color=_to_hex(darkened_color),
        privacy_icon_color_dark=corrected_hex,
    )
