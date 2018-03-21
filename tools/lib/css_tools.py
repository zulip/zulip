import colorsys
import re

def is_color_scheme(declaration, fn):
    color_properties = [
        'background',
        'background-color',
        'border-bottom-color',
        'border-color',
        'border-left-color',
        'border-right-color',
        'border-top-color',
        'box-shadow',
        'color',
        'fill',
        'font-color',
        'outline-color',
        'stroke',
    ]

    if 'bootstrap' in fn:
        color_properties += [
            'border',
        ]

    value = declaration.css_value.text().strip()

    if declaration.css_property not in color_properties:
        if 'hsl' in value:
            # raise 'foo'
            pass
        return False


    if 'bootstrap' in fn:
        # yay, bootstrap :(
        if ' \\9' in value:
            return False

    if 'gradient' in value:
        return False

    if value == '0':
        return False

    if 'transparent' in value:
        return False

    if 'inherit' in value:
        return False

    if 'none' in value:
        return False

    if '\n' in value:
        return False

    if 'Microsoft' in value:
        return False

    return True

def dec(hex):
    return int(hex, 16)

def perc(f):
    p = str(int(100 * f))
    return p + '%'

def to_hsl(r, g, b):
    r = r / 255.0
    g = g / 255.0
    b = b / 255.0

    if (r > 1) or (g > 1) or (b > 1):
        raise 'foo'

    if (r < 0) or (g < 0) or (b < 0):
        raise 'foo'

    (h, l, s) = colorsys.rgb_to_hls(r, g, b)
    h = int(360 * h)
    s = perc(s)
    l = perc(l)
    return h, s, l

def rgb(m, value):
    value = '#' + value[1] + value[1] + value[2] + value[2] + value[3] + value[3]
    return rrggbb(m, value)

def rrggbb(m, value):
    r = dec(value[1:3])
    g = dec(value[3:5])
    b = dec(value[5:7])
    h, s, l = to_hsl(r, g, b)
    value = 'hsl(%d, %s, %s)' % (h, s, l)
    return value

def rgba(m, value):
    r, g, b, a = m.groups()
    h, s, l = to_hsl(int(r), int(g), int(b))
    value = 'hsla(%d, %s, %s, %s)' % (h, s, l, a)
    return value

def same(m, value):
    return value

CONVERTERS = [
    ('#[0-9a-fA-f]{6}', rrggbb),
    ('#[0-9a-fA-f]{3}', rgb),
    ('rgba\((.*?), (.*?), (.*?), (.*.?)\)$', rgba),
    ('hsla?\([^(]+?\)', same),
]

def convert_colors(value):
    map = dict(
        aliceblue='#f0f8ff',
        black='#000000',
        blue='#0000ff',
        gray='#808080',
        lightblue='#add8e6',
        maroon='#800000',
        purple='#800080',
        red='#ff0000',
        white='#ffffff',
    )

    if value in map:
        value = map[value]

    for regex, f in CONVERTERS:
        m = re.match(regex, value)
        if m:
            return f(m, value)

    for regex, f in CONVERTERS:
        m = re.search(regex, value)
        if m:
            bef = value[:m.start()]
            s = value[m.start():m.end()]
            aft = value[m.end():]
            return bef + f(m, s) + maybe_convert_colors(aft)

    return value

def maybe_convert_colors(s):
    if s == '':
        return s
    return convert_colors(s)

def invert_light(lum):
    lum = int(100 - float(lum))
    lum = int(10 + 0.9 * lum)
    return lum

def invert_hsl(h, s, l):
    h = int(h)

    l = invert_light(l)
    if (l < 25):
        h = 180
    return h, s, l

def invert_HSL(m, value):
    h, s, l, a = m.groups()
    h, s, l = invert_hsl(h, s, l)
    value = 'hsla(%s, %s, %s%%, %s)' % (h, s, l, a)
    return value

def invert_HSLA(m, value):
    h, s, l = m.groups()
    h, s, l = invert_hsl(h, s, l)
    value = 'hsl(%s, %s, %s%%)' % (h, s, l)
    return value

INVERTERS = [
    ('hsla\((.*?), (.*?), (.*?)%, (.*.?)\)', invert_HSL),
    ('hsl\((.*?), (.*?), (.*?)%\)', invert_HSLA),
]

def invert(value):
    for regex, f in INVERTERS:
        m = re.search(regex, value)
        if m:
            bef = value[:m.start()]
            s = value[m.start():m.end()]
            aft = value[m.end():]
            return bef + f(m, s) + invert(aft)
    return value

