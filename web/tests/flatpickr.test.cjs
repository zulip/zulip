"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const {initialize_user_settings} = zrequire("user_settings");

const user_settings = {};
initialize_user_settings({user_settings});

const flatpickr = zrequire("flatpickr");
const custom_profile_fields_ui = zrequire("custom_profile_fields_ui");

run_test("get_flatpickr_locale", ({override}) => {
    // Exact matches
    assert.equal(flatpickr.get_flatpickr_locale("fr").weekdays.shorthand[0], "dim");
    assert.equal(flatpickr.get_flatpickr_locale("de").weekdays.shorthand[0], "So");
    assert.equal(flatpickr.get_flatpickr_locale("en").weekdays.shorthand[0], "Sun");

    // Special mappings
    assert.equal(flatpickr.get_flatpickr_locale("zh-hans").weekdays.shorthand[0], "周日");
    assert.equal(flatpickr.get_flatpickr_locale("zh-tw").weekdays.shorthand[0], "週日");
    assert.equal(flatpickr.get_flatpickr_locale("el").weekdays.shorthand[0], "Κυ");
    assert.equal(flatpickr.get_flatpickr_locale("kk").weekdays.shorthand[0], "Жс");
    assert.equal(flatpickr.get_flatpickr_locale("vi").weekdays.shorthand[0], "CN");

    // Base fallback
    assert.equal(flatpickr.get_flatpickr_locale("pt-pt").weekdays.shorthand[0], "Dom");
    assert.equal(flatpickr.get_flatpickr_locale("en-gb").weekdays.shorthand[0], "Sun");

    // Fallback for unsupported or unknown language
    assert.equal(flatpickr.get_flatpickr_locale("unsupported-lang"), undefined);
    assert.equal(flatpickr.get_flatpickr_locale(""), undefined);

    // Default to user_settings.default_language
    override(user_settings, "default_language", "fr");
    assert.equal(flatpickr.get_flatpickr_locale().weekdays.shorthand[0], "dim");

    override(user_settings, "default_language", "de");
    assert.equal(flatpickr.get_flatpickr_locale().weekdays.shorthand[0], "So");
});

run_test("custom_profile_fields_ui format_date localization", ({override}) => {
    const test_date = new Date(2026, 0, 15);

    // Default English
    override(user_settings, "default_language", "en");
    assert.equal(custom_profile_fields_ui.format_date(test_date, "F j, Y"), "January 15, 2026");

    // French localization
    override(user_settings, "default_language", "fr");
    assert.equal(custom_profile_fields_ui.format_date(test_date, "F j, Y"), "janvier 15, 2026");

    // Spanish localization
    override(user_settings, "default_language", "es");
    assert.equal(custom_profile_fields_ui.format_date(test_date, "F j, Y"), "Enero 15, 2026");

    // Explicit locale parameter overrides user_settings
    const french_locale = flatpickr.get_flatpickr_locale("fr");
    override(user_settings, "default_language", "en");
    assert.equal(
        custom_profile_fields_ui.format_date(test_date, "F j, Y", french_locale),
        "janvier 15, 2026",
    );

    // Invalid dates remain unchanged
    assert.equal(custom_profile_fields_ui.format_date(undefined, "F j, Y"), "Invalid Date");
    assert.equal(
        custom_profile_fields_ui.format_date(new Date("invalid"), "F j, Y"),
        "Invalid Date",
    );
});
