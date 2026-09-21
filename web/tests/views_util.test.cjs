"use strict";

const assert = require("node:assert/strict");

const {zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");

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
