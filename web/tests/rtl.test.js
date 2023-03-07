"use strict";

const {strict: assert} = require("assert");

const {zrequire} = require("./lib/namespace");
const {run_test} = require("./lib/test");
const $ = require("./lib/zjquery");

const rtl = zrequire("rtl");

run_test("get_direction", () => {
    // These characters are strong R or AL:    ا ب پ ج ض و د ؛
    // These characters are not strong:        ۱ ۲ ۳ ۴ ۵ ۶ ۷ ۸ ۹ ۰

    assert.equal(rtl.get_direction("abcابپ"), "ltr");
    assert.equal(rtl.get_direction("ابپabc"), "rtl");
    assert.equal(rtl.get_direction("123abc"), "ltr");
    assert.equal(rtl.get_direction("۱۲۳abc"), "ltr");
    assert.equal(rtl.get_direction("123؛بپ"), "rtl");
    assert.equal(rtl.get_direction("۱۲۳ابپ"), "rtl");
    assert.equal(rtl.get_direction("۱۲جg"), "rtl");
    assert.equal(rtl.get_direction("12gج"), "ltr");
    assert.equal(rtl.get_direction("۱۲۳"), "ltr");
    assert.equal(rtl.get_direction("1234"), "ltr");

    const supp_plane_ltr_char = "\uD800\uDFA0";
    const supp_plane_rtl_char = "\uD802\uDC40";

    assert.equal(rtl.get_direction(supp_plane_ltr_char), "ltr");
    assert.equal(rtl.get_direction(supp_plane_rtl_char), "rtl");
    assert.equal(rtl.get_direction("123" + supp_plane_ltr_char), "ltr");
    assert.equal(rtl.get_direction("123" + supp_plane_rtl_char), "rtl");
    assert.equal(rtl.get_direction(supp_plane_ltr_char + supp_plane_rtl_char), "ltr");
    assert.equal(rtl.get_direction(supp_plane_rtl_char + supp_plane_ltr_char), "rtl");
    assert.equal(rtl.get_direction(supp_plane_ltr_char + " " + supp_plane_rtl_char), "ltr");
    assert.equal(rtl.get_direction(supp_plane_rtl_char + " " + supp_plane_ltr_char), "rtl");
    assert.equal(rtl.get_direction(supp_plane_ltr_char + "ج" + supp_plane_rtl_char), "ltr");
    assert.equal(rtl.get_direction(supp_plane_rtl_char + "ج" + supp_plane_ltr_char), "rtl");
    assert.equal(rtl.get_direction("پ" + supp_plane_ltr_char + "." + supp_plane_rtl_char), "rtl");
    assert.equal(rtl.get_direction("پ" + supp_plane_rtl_char + "." + supp_plane_ltr_char), "rtl");
    assert.equal(rtl.get_direction("b" + supp_plane_ltr_char + "." + supp_plane_rtl_char), "ltr");
    assert.equal(rtl.get_direction("b" + supp_plane_rtl_char + "." + supp_plane_ltr_char), "ltr");

    const unmatched_surrogate_1 = "\uD800";
    const unmatched_surrogate_2 = "\uDF00";

    assert.equal(rtl.get_direction(unmatched_surrogate_1 + " "), "ltr");
    assert.equal(rtl.get_direction(unmatched_surrogate_2 + " "), "ltr");
    assert.equal(rtl.get_direction(" " + unmatched_surrogate_1), "ltr");
    assert.equal(rtl.get_direction(" " + unmatched_surrogate_2), "ltr");
    assert.equal(rtl.get_direction(" " + unmatched_surrogate_1 + " "), "ltr");
    assert.equal(rtl.get_direction(" " + unmatched_surrogate_2 + " "), "ltr");
    assert.equal(rtl.get_direction(unmatched_surrogate_1 + supp_plane_ltr_char), "ltr");
    assert.equal(rtl.get_direction(unmatched_surrogate_1 + supp_plane_rtl_char), "ltr");
    assert.equal(rtl.get_direction(unmatched_surrogate_2 + supp_plane_ltr_char), "ltr");
    assert.equal(rtl.get_direction(unmatched_surrogate_2 + supp_plane_rtl_char), "ltr");
    assert.equal(rtl.get_direction(supp_plane_ltr_char + unmatched_surrogate_1), "ltr");
    assert.equal(rtl.get_direction(supp_plane_ltr_char + unmatched_surrogate_2), "ltr");
    assert.equal(rtl.get_direction(supp_plane_rtl_char + unmatched_surrogate_1), "rtl");
    assert.equal(rtl.get_direction(supp_plane_rtl_char + unmatched_surrogate_2), "rtl");

    // Testing with some isolate initiators and PDIs.
    const i_chars = "\u2066\u2067\u2068";
    const pdi = "\u2069";

    assert.equal(rtl.get_direction("aa" + i_chars.charAt(0) + "bb" + pdi + "cc"), "ltr");
    assert.equal(rtl.get_direction("دد" + i_chars.charAt(0) + "bb" + pdi + "cc"), "rtl");
    assert.equal(rtl.get_direction("12" + i_chars.charAt(0) + "bb" + pdi + "جج"), "rtl");
    assert.equal(rtl.get_direction("۱۲" + i_chars.charAt(0) + "جج" + pdi + "cc"), "ltr");
    assert.equal(rtl.get_direction("aa" + i_chars.charAt(0) + "ج؛ج"), "ltr");
    assert.equal(rtl.get_direction("12" + i_chars.charAt(0) + "ج؛ج"), "ltr");
    assert.equal(rtl.get_direction("۱۲" + i_chars.charAt(0) + "aaa"), "ltr");
    assert.equal(
        rtl.get_direction(
            ",," + i_chars.charAt(0) + "bb" + i_chars.charAt(0) + "جج" + pdi + "ضض" + pdi + "..",
        ),
        "ltr",
    );
    assert.equal(
        rtl.get_direction(
            ",," + i_chars.charAt(0) + "bb" + i_chars.charAt(0) + "جج" + pdi + "ضض" + pdi + "وو",
        ),
        "rtl",
    );
    assert.equal(
        rtl.get_direction(",," + i_chars.charAt(0) + "bb" + pdi + "33" + pdi + ".."),
        "ltr",
    );
    assert.equal(
        rtl.get_direction(",," + i_chars.charAt(0) + "bb" + pdi + "12" + pdi + "وو"),
        "rtl",
    );
    assert.equal(
        rtl.get_direction(",," + i_chars.charAt(0) + "ضج" + pdi + "12" + pdi + "ff"),
        "ltr",
    );

    assert.equal(rtl.get_direction("aa" + i_chars.charAt(1) + "bb" + pdi + "cc"), "ltr");
    assert.equal(rtl.get_direction("دد" + i_chars.charAt(2) + "bb" + pdi + "cc"), "rtl");
    assert.equal(rtl.get_direction("12" + i_chars.charAt(1) + "bb" + pdi + "جج"), "rtl");
    assert.equal(rtl.get_direction("۱۲" + i_chars.charAt(2) + "جج" + pdi + "cc"), "ltr");
    assert.equal(rtl.get_direction("aa" + i_chars.charAt(1) + "ججج"), "ltr");
    assert.equal(rtl.get_direction("12" + i_chars.charAt(2) + "ججج"), "ltr");
    assert.equal(rtl.get_direction("۱۲" + i_chars.charAt(1) + "aaa"), "ltr");
    assert.equal(
        rtl.get_direction(
            ",," + i_chars.charAt(1) + "bb" + i_chars.charAt(2) + "جج" + pdi + "ضض" + pdi + "..",
        ),
        "ltr",
    );
    assert.equal(
        rtl.get_direction(
            ",," + i_chars.charAt(2) + "bb" + i_chars.charAt(1) + "؛ج" + pdi + "ضض" + pdi + "وو",
        ),
        "rtl",
    );
    assert.equal(
        rtl.get_direction(",," + i_chars.charAt(1) + "bb" + pdi + "33" + pdi + ".."),
        "ltr",
    );
    assert.equal(
        rtl.get_direction(",," + i_chars.charAt(2) + "bb" + pdi + "12" + pdi + "وو"),
        "rtl",
    );
    assert.equal(
        rtl.get_direction(",," + i_chars.charAt(1) + "ضج" + pdi + "12" + pdi + "ff"),
        "ltr",
    );
});

run_test("set_rtl_class_for_textarea rtl", () => {
    const $textarea = $.create("some-textarea");
    assert.ok(!$textarea.hasClass("rtl"));
    const text = "```quote\nمرحبا";
    $textarea.val(text);
    rtl.set_rtl_class_for_textarea($textarea);
    assert.ok($textarea.hasClass("rtl"));
});

run_test("set_rtl_class_for_textarea ltr", () => {
    const $textarea = $.create("some-textarea");
    $textarea.addClass("rtl");
    assert.ok($textarea.hasClass("rtl"));
    const text = "```quote\nEnglish text";
    $textarea.val(text);
    rtl.set_rtl_class_for_textarea($textarea);
    assert.ok(!$textarea.hasClass("rtl"));
});
