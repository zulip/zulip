"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

const settings_account = zrequire("settings_account");

run_test("update_custom_profile_field", () => {
    // Test with already formatted ISO date
    const isoDate = "2025-05-20";
    assert.equal(
        settings_account.parse_to_iso_date_format(isoDate),
        isoDate,
        "Should return already formatted ISO date unchanged",
    );

    // Test with natural language date
    const naturalDate = "March 20, 2025";
    assert.equal(
        settings_account.parse_to_iso_date_format(naturalDate),
        "2025-03-20",
        "Should parse natural language date to ISO format",
    );

    // Test with invalid date string
    const invalidDate = "not a date";
    assert.equal(
        settings_account.parse_to_iso_date_format(invalidDate),
        invalidDate,
        "Should return invalid date string unchanged",
    );

    // Test with date that has single-digit month/day
    const singleDigitDate = "January 5, 2025";
    assert.equal(
        settings_account.parse_to_iso_date_format(singleDigitDate),
        "2025-01-05",
        "Should pad single-digit months/days with leading zero",
    );
});
