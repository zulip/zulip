"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const flatpickr = zrequire("flatpickr");

function override_default_locale(override, locale) {
    override(Intl, "DateTimeFormat", () => ({resolvedOptions: () => ({locale})}));
}

run_test("get_first_day_of_week", ({override}) => {
    override_default_locale(override, "en-US");
    assert.equal(flatpickr.get_first_day_of_week(), 0);

    override_default_locale(override, "en-GB");
    assert.equal(flatpickr.get_first_day_of_week(), 1);

    override_default_locale(override, "ar-EG");
    assert.equal(flatpickr.get_first_day_of_week(), 6);

    // Without a region, the locale's likely region is used.
    override_default_locale(override, "de");
    assert.equal(flatpickr.get_first_day_of_week(), 1);
});

run_test("get_first_day_of_week without getWeekInfo", ({override}) => {
    // Older Chrome and Safari versions only have the weekInfo getter.
    override(Intl, "Locale", () => ({weekInfo: {firstDay: 1}}));
    assert.equal(flatpickr.get_first_day_of_week(), 1);

    // Without either, we fall back to flatpickr's default.
    override(Intl, "Locale", () => ({}));
    assert.equal(flatpickr.get_first_day_of_week(), 0);
});
