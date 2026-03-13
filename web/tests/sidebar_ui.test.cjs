"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test, noop} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");
const {FakeJQuery} = require("./lib/zjquery_element.cjs");

set_global("document", "document-stub");

FakeJQuery.prototype.not = function () {
    return this;
};

let current_search_term = "";
let current_topics_state = "";
let current_narrow_stream_id;
let current_narrow_topic;
let update_streams_sidebar_calls = 0;

mock_esm("../src/left_sidebar_filter", {
    clear_left_sidebar_filter: noop,
    clear_query_without_updating: noop,
    get_effective_topics_state_for_search: () => current_topics_state,
    is_typeahead_shown: noop,
    setup_left_sidebar_filter_typeahead: noop,
});
mock_esm("../src/left_sidebar_navigation_area", {
    expand_views: noop,
    get_built_in_views: () => [],
    reorder_left_sidebar_navigation_list: noop,
    restore_views_state: noop,
    update_reminders_row: noop,
    update_scheduled_messages_row: noop,
});
mock_esm("../src/narrow_state", {
    stream_id: () => current_narrow_stream_id,
    topic: () => current_narrow_topic,
});
mock_esm("../src/pm_list", {
    update_private_messages: noop,
});
mock_esm("../src/resize", {
    resize_page_components: noop,
    resize_stream_filters_container: noop,
});
mock_esm("../src/stream_list", {
    update_streams_sidebar() {
        update_streams_sidebar_calls += 1;
    },
});
mock_esm("../src/ui_util", {
    get_left_sidebar_search_term: () => current_search_term,
    matches_viewport_state: noop,
});

const sidebar_ui = zrequire("sidebar_ui");

function stub_all_rows() {
    const selectors = [
        ".top_left_row, " +
            ".bottom_left_row, " +
            "#left-sidebar-navigation-area:not(.hidden-by-filters) #views-label-container, " +
            "#left_sidebar_scroll_container:not(.direct-messages-hidden-by-filters) #direct-messages-section-header, " +
            ".stream-list-section-container:not(.no-display) .stream-list-subsection-header",
        "#streams_list:not(.is_searching) .stream-list-section-container:not(.showing-inactive-or-muted)" +
            " .inactive-or-muted-in-channel-folder .bottom_left_row:not(.hidden-by-filters)",
        "#views-label-container.showing-condensed-navigation +" +
            " #left-sidebar-navigation-list .top_left_row",
        ".stream-list-section-container.collapsed .narrow-filter:not(.stream-expanded) .bottom_left_row",
        ".stream-list-section-container.collapsed .topic-list-item:not(.active-sub-filter).bottom_left_row",
        "#streams_list.is_searching .stream-list-toggle-inactive-or-muted-channels.bottom_left_row",
    ];

    for (const selector of selectors) {
        const $rows = $(selector);
        $rows.length = 0;
    }
}

run_test(
    "refresh_left_sidebar_search_for_narrow_change_rebuilds_for_narrow_context_change",
    ({override_rewire}) => {
        override_rewire(sidebar_ui, "left_sidebar_cursor", {
            clear: noop,
            reset: noop,
            set_is_highlight_visible: noop,
        });
        stub_all_rows();

        update_streams_sidebar_calls = 0;
        current_search_term = "devel";
        current_topics_state = "";
        current_narrow_stream_id = 5;
        current_narrow_topic = "old topic";

        sidebar_ui.refresh_left_sidebar_search_for_narrow_change();
        assert.equal(update_streams_sidebar_calls, 1);

        current_narrow_stream_id = 10;
        current_narrow_topic = "new topic";

        sidebar_ui.refresh_left_sidebar_search_for_narrow_change();

        assert.equal(update_streams_sidebar_calls, 2);
    },
);

run_test(
    "refresh_left_sidebar_search_for_narrow_change_skips_unchanged_context",
    ({override_rewire}) => {
        override_rewire(sidebar_ui, "left_sidebar_cursor", {
            clear: noop,
            reset: noop,
            set_is_highlight_visible: noop,
        });
        stub_all_rows();

        update_streams_sidebar_calls = 0;
        current_search_term = "social";
        current_topics_state = "is:followed";
        current_narrow_stream_id = 10;
        current_narrow_topic = "topic";

        sidebar_ui.refresh_left_sidebar_search_for_narrow_change();
        assert.equal(update_streams_sidebar_calls, 1);

        sidebar_ui.refresh_left_sidebar_search_for_narrow_change();

        assert.equal(update_streams_sidebar_calls, 1);
    },
);
