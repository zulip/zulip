zrequire('colorspace');

run_test('sRGB_to_linear', () => {
    var srgb_color = 0.0042;
    var expected_value = 0.0042 / 255.0 / 12.92;
    var actual_value = colorspace.sRGB_to_linear(srgb_color);
    assert.equal(actual_value, expected_value);

    srgb_color = 255.0;
    expected_value = 1;
    actual_value = colorspace.sRGB_to_linear(srgb_color);
    assert.equal(actual_value, expected_value);
});

run_test('rgb_luminance', () => {
    var channel = [1, 1, 1];
    var expected_value = 1;
    var actual_value = colorspace.rgb_luminance(channel);
    assert.equal(actual_value, expected_value);
});

run_test('luminance_to_lightness', () => {
    var luminance = 0;
    var expected_value  = 116 * 4 / 29 - 16;
    var actual_value = colorspace.luminance_to_lightness(luminance);
    assert.equal(actual_value, expected_value);

    luminance = 1;
    expected_value = 100;
    actual_value = colorspace.luminance_to_lightness(luminance);
    assert.equal(actual_value, expected_value);
});

run_test('getDecimalColor', () => {
    var hex_color = '#1f293b';
    var expected_value = {
        r: 31,
        g: 41,
        b: 59,
    };
    var actual_value = colorspace.getDecimalColor(hex_color);
    assert.deepEqual(actual_value, expected_value);
});

run_test('getLighterColor', () => {
    var rgb_color = {
        r: 31,
        g: 41,
        b: 59,
    };
    var lightness = 0;
    var expected_value = rgb_color;
    var actual_value = colorspace.getLighterColor(rgb_color, lightness);
    assert.deepEqual(actual_value, expected_value);
});

run_test('getHexColor', () => {
    var rgb_color = {
        r: 31,
        g: 41,
        b: 59,
    };
    var expected_value = '#1f293b';
    var actual_value = colorspace.getHexColor(rgb_color);
    assert.equal(actual_value, expected_value);
});


