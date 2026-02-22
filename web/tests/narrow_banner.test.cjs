"use strict";

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// Mock narrow_error so we don’t render real HTML
mock_esm("../src/narrow_error.ts", {
    narrow_error() {
        return "<div></div>";
    },
});

const narrow_banner = zrequire("narrow_banner");

run_test("narrow_banner functions execute without crashing", () => {
    // Covers hide_empty_narrow_message
    narrow_banner.hide_empty_narrow_message();

    // Covers show_error_message
    narrow_banner.show_error_message("Test error");

    // Filter that hits is_in_home === true path
    narrow_banner.show_empty_narrow_message({
        is_in_home() {
            return true;
        },
        terms() {
            return [];
        },
        sorted_term_types() {
            return [];
        },
        terms_with_operator() {
            return [];
        },
    });

    // Filter that hits is_in_home === false path
    narrow_banner.show_empty_narrow_message({
        is_in_home() {
            return false;
        },
        terms() {
            return [];
        },
        sorted_term_types() {
            return [];
        },
        terms_with_operator() {
            return [];
        },
    });
});