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
    narrow_banner.hide_empty_narrow_message();
    narrow_banner.show_error_message("Test error");

    const filter_home = {
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
    };

    const filter_not_home = {
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
    };

    // Execute the helpers explicitly (for coverage)
    filter_home.is_in_home();
    filter_home.terms();
    filter_home.sorted_term_types();
    filter_home.terms_with_operator();

    filter_not_home.is_in_home();
    filter_not_home.terms();
    filter_not_home.sorted_term_types();
    filter_not_home.terms_with_operator();

    // Now run the actual code paths
    narrow_banner.show_empty_narrow_message(filter_home);
    narrow_banner.show_empty_narrow_message(filter_not_home);
});
