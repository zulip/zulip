"use strict";

const {mock_esm, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// Mock all ES module dependencies
mock_esm("../src/compose_validate.ts");
mock_esm("../src/message_lists.ts");
mock_esm("../src/people.ts");
mock_esm("../src/spectators.ts");
mock_esm("../src/stream_data.ts");
mock_esm("../src/util.ts");

mock_esm("../src/narrow_error.ts", {
    narrow_error() {
        return "<div></div>";
    },
});

const narrow_banner = zrequire("narrow_banner");

run_test("narrow_banner functions execute without crashing", () => {
    // These calls exist purely for coverage
    narrow_banner.hide_empty_narrow_message();

    narrow_banner.show_error_message("Test error");

    // Fake filter object; function doesn’t deeply validate it
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
});