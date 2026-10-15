"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {noop, run_test} = require("./lib/test.cjs");

set_global("to_$", () => ({width: () => 1440}));

mock_esm("../src/compose_ui", {
    autosize_textarea: noop,
    maybe_show_scrolling_formatting_buttons: noop,
});
mock_esm("../src/condense", {condense_and_collapse: noop});
mock_esm("../src/message_lists", {
    all_current_message_rows: noop,
    current: undefined,
});
mock_esm("../src/resize", {
    resize_page_components: noop,
    update_recent_view: noop,
});
mock_esm("../src/scroll_bar", {handle_overlay_scrollbars: noop});
const sidebar_ui = mock_esm("../src/sidebar_ui");
const ui_util = mock_esm("../src/ui_util");
const util = mock_esm("../src/util");

const resize_handler = zrequire("resize_handler");

run_test("sidebar toggle state is recomputed on resize", ({override}) => {
    let update_aria_expanded_calls = 0;
    override(util, "is_mobile", () => false);
    override(ui_util, "matches_viewport_state", () => true);
    override(sidebar_ui, "update_sidebar_aria_expanded", () => {
        update_aria_expanded_calls += 1;
    });

    // Crossing the right sidebar's breakpoint doesn't change whether
    // the left sidebar is an overlay, so no sidebar gets hidden, but
    // the toggle buttons still need to reflect the new layout.
    resize_handler.handler();
    assert.equal(update_aria_expanded_calls, 1);
});
