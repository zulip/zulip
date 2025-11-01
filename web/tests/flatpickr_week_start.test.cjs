"use strict";

const assert = require("node:assert/strict");

const {zrequire, set_global} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

set_global("navigator", {language: "en-US"});

const {initialize_user_settings} = zrequire("user_settings");
const {get_first_day_of_week} = zrequire("../src/flatpickr");

function set_week_start_day(code) {
    initialize_user_settings({user_settings: {week_start_day: code}});
}

run_test("explicit mappings", () => {
    set_week_start_day(2); // Saturday
    assert.equal(get_first_day_of_week(), 6);

    set_week_start_day(3); // Sunday
    assert.equal(get_first_day_of_week(), 0);

    set_week_start_day(4); // Monday
    assert.equal(get_first_day_of_week(), 1);
});

run_test("automatic locales", ({override}) => {
    // en-GB should map to Monday via Intl.Locale.getWeekInfo().firstDay = 1
    set_global("navigator", {language: "en-GB"});
    override(Intl, "Locale", () => ({getWeekInfo: () => ({firstDay: 1})}));
    set_week_start_day(1); // Automatic
    assert.equal(get_first_day_of_week(), 1);

    // en-US should fall back to CLDR (weekstart)
    set_global("navigator", {language: "en-US"});
    override(Intl, "Locale", () => ({}));
    set_week_start_day(1);
    assert.equal(get_first_day_of_week(), 0);
});

run_test("automatic fallback", () => {
    set_week_start_day(1); // Automatic
    assert.equal(get_first_day_of_week(), 0);
});
