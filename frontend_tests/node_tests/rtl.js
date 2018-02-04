zrequire('util');
var rtl = zrequire('rtl');

(function test_get_direction() {
    // These characters are strong R or AL:    ا ب پ ج ض و د ؛
    // These characters are not strong:        ۱ ۲ ۳ ۴ ۵ ۶ ۷ ۸ ۹ ۰

    assert.equal(rtl.get_direction('abcابپ'), 'ltr');
    assert.equal(rtl.get_direction('ابپabc'), 'rtl');
    assert.equal(rtl.get_direction('123abc'), 'ltr');
    assert.equal(rtl.get_direction('۱۲۳abc'), 'ltr');
    assert.equal(rtl.get_direction('123؛بپ'), 'rtl');
    assert.equal(rtl.get_direction('۱۲۳ابپ'), 'rtl');
    assert.equal(rtl.get_direction('۱۲جg'), 'rtl');
    assert.equal(rtl.get_direction('12gج'), 'ltr');
    assert.equal(rtl.get_direction('۱۲۳'), 'ltr');
    assert.equal(rtl.get_direction('1234'), 'ltr');

    // Testing with some isolate initiators and PDIs.
    var i_chars = '\u2066\u2067\u2068';
    var pdi = '\u2069';

    assert.equal(rtl.get_direction('aa' + i_chars.charAt(0) + 'bb' + pdi + 'cc'), 'ltr');
    assert.equal(rtl.get_direction('دد' + i_chars.charAt(0) + 'bb' + pdi + 'cc'), 'rtl');
    assert.equal(rtl.get_direction('12' + i_chars.charAt(0) + 'bb' + pdi + 'جج'), 'rtl');
    assert.equal(rtl.get_direction('۱۲' + i_chars.charAt(0) + 'جج' + pdi + 'cc'), 'ltr');
    assert.equal(rtl.get_direction('aa' + i_chars.charAt(0) + 'ج؛ج'), 'ltr');
    assert.equal(rtl.get_direction('12' + i_chars.charAt(0) + 'ج؛ج'), 'ltr');
    assert.equal(rtl.get_direction('۱۲' + i_chars.charAt(0) + 'aaa'), 'ltr');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(0) + 'bb' + i_chars.charAt(0) + 'جج' + pdi + 'ضض' + pdi + '..'), 'ltr');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(0) + 'bb' + i_chars.charAt(0) + 'جج' + pdi + 'ضض' + pdi + 'وو'), 'rtl');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(0) + 'bb' + pdi + '33' + pdi + '..'), 'ltr');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(0) + 'bb' + pdi + '12' + pdi + 'وو'), 'rtl');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(0) + 'ضج' + pdi + '12' + pdi + 'ff'), 'ltr');

    assert.equal(rtl.get_direction('aa' + i_chars.charAt(1) + 'bb' + pdi + 'cc'), 'ltr');
    assert.equal(rtl.get_direction('دد' + i_chars.charAt(2) + 'bb' + pdi + 'cc'), 'rtl');
    assert.equal(rtl.get_direction('12' + i_chars.charAt(1) + 'bb' + pdi + 'جج'), 'rtl');
    assert.equal(rtl.get_direction('۱۲' + i_chars.charAt(2) + 'جج' + pdi + 'cc'), 'ltr');
    assert.equal(rtl.get_direction('aa' + i_chars.charAt(1) + 'ججج'), 'ltr');
    assert.equal(rtl.get_direction('12' + i_chars.charAt(2) + 'ججج'), 'ltr');
    assert.equal(rtl.get_direction('۱۲' + i_chars.charAt(1) + 'aaa'), 'ltr');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(1) + 'bb' + i_chars.charAt(2) + 'جج' + pdi + 'ضض' + pdi + '..'), 'ltr');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(2) + 'bb' + i_chars.charAt(1) + '؛ج' + pdi + 'ضض' + pdi + 'وو'), 'rtl');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(1) + 'bb' + pdi + '33' + pdi + '..'), 'ltr');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(2) + 'bb' + pdi + '12' + pdi + 'وو'), 'rtl');
    assert.equal(rtl.get_direction(',,' + i_chars.charAt(1) + 'ضج' + pdi + '12' + pdi + 'ff'), 'ltr');
}());
