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

run_test("get_first_day_of_week prefers getWeekInfo", ({override}) => {
    override(Intl, "Locale", () => ({
        getWeekInfo: () => ({firstDay: 7}),
        get weekInfo() {
            throw new Error("The legacy getter should not be read when getWeekInfo is available.");
        },
    }));
    assert.equal(flatpickr.get_first_day_of_week(), 0);
});

run_test("get_first_day_of_week with the legacy weekInfo getter", ({override}) => {
    override_default_locale(override, "en-GB");
    override(Intl, "Locale", (locale) => {
        assert.equal(locale, "en-GB");
        return {
            get weekInfo() {
                return {firstDay: 1};
            },
        };
    });
    assert.equal(flatpickr.get_first_day_of_week(), 1);
});

run_test("get_first_day_of_week without either week info API", ({override}) => {
    override(Intl, "Locale", () => ({}));
    assert.equal(flatpickr.get_first_day_of_week(), 0);
});

run_test("get_first_day_of_week without Intl.Locale", ({override}) => {
    override(Intl, "Locale", undefined);
    assert.equal(flatpickr.get_first_day_of_week(), 0);
});
