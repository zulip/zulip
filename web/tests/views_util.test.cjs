"use strict";

const assert = require("node:assert/strict");

const {mock_jquery, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

// views_util reads the page's bottom padding from a CSS variable.
const bottom_padding = 400;
mock_jquery(() => ({css: () => `${bottom_padding}px`}));

const views_util = zrequire("views_util");

function make_row(top, height = 30) {
    return {
        getBoundingClientRect: () => ({top, bottom: top + height}),
    };
}

run_test("find_first_row_index_at_or_below", () => {
    // Two adjacent rows, then a gap like the margin between two
    // sections of Inbox, a row, and a smaller gap like the one below
    // a folder header.
    const rows = [make_row(100), make_row(130), make_row(168), make_row(199.5)];
    const find_row_index = (y) => views_util.find_first_row_index_at_or_below(rows, y);

    assert.equal(find_row_index(50), 0);
    assert.equal(find_row_index(145), 1);
    assert.equal(find_row_index(175), 2);
    assert.equal(find_row_index(210), 3);
    // A point on the edge between two adjacent rows selects the lower one.
    assert.equal(find_row_index(130), 1);
    // A point in a gap, including its top edge, selects the row just
    // below the gap.
    assert.equal(find_row_index(160), 2);
    assert.equal(find_row_index(162), 2);
    assert.equal(find_row_index(198.5), 3);
    // A point at or below the bottom edge of the last row selects no row.
    assert.equal(find_row_index(229.5), undefined);
    assert.equal(find_row_index(500), undefined);
    assert.equal(views_util.find_first_row_index_at_or_below([], 145), undefined);
});

run_test("is_bottom_padding_in_view", () => {
    const viewport_bottom = 600;
    window.scrollY = 100;
    window.innerHeight = viewport_bottom - window.scrollY;
    const body = {scrollHeight: viewport_bottom + 1 + bottom_padding};
    set_global("document", {body});

    // The rows end just below the bottom of the viewport, then at it.
    assert.ok(!views_util.is_bottom_padding_in_view());
    body.scrollHeight -= 1;
    assert.ok(views_util.is_bottom_padding_in_view());
});
