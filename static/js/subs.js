"use strict";

const _ = require("lodash");

const render_subscription = require("../templates/subscription.hbs");
const render_subscription_settings = require("../templates/subscription_settings.hbs");
const render_subscription_table_body = require("../templates/subscription_table_body.hbs");
const render_subscriptions = require("../templates/subscriptions.hbs");

const people = require("./people");
const util = require("./util");

exports.show_subs_pane = {
    nothing_selected() {
        $(".stream-info-title, .settings, #stream-creation").hide();
        $("#stream_settings_title, .nothing-selected").show();
    },
    settings() {
        $(".stream-info-title, .settings, #stream-creation").hide();
        $("#stream_settings_title, .settings").show();
    },
    create_stream() {
        $(".stream-info-title, .nothing-selected, .settings, #stream-creation").hide();
        $("#add_new_stream_title, #stream-creation").show();
    },
};

exports.check_button_for_sub = function (sub) {
    return $(".stream-row[data-stream-id='" + sub.stream_id + "'] .check");
};

exports.row_for_stream_id = function (stream_id) {
    return $(".stream-row[data-stream-id='" + stream_id + "']");
};

exports.settings_button_for_sub = function (sub) {
    // We don't do expectOne() here, because this button is only
    // visible if the user has that stream selected in the streams UI.
    return $(".subscription_settings[data-stream-id='" + sub.stream_id + "'] .subscribe-button");
};

function get_row_data(row) {
    const row_id = parseInt(row.attr("data-stream-id"), 10);
    if (row_id) {
        const row_object = stream_data.get_sub_by_id(row_id);
        return {
            id: row_id,
            object: row_object,
        };
    }
}

exports.get_active_data = function () {
    const active_row = $("div.stream-row.active");
    const valid_active_id = parseInt(active_row.attr("data-stream-id"), 10);
    const active_tabs = $(".subscriptions-container").find("div.ind-tab.selected");
    return {
        row: active_row,
        id: valid_active_id,
        tabs: active_tabs,
    };
};

function get_hash_safe() {
    if (typeof window !== "undefined" && typeof window.location.hash === "string") {
        return window.location.hash.substr(1);
    }

    return "";
}

function selectText(element) {
    let range;
    let sel;
    if (window.getSelection) {
        sel = window.getSelection();
        range = document.createRange();
        range.selectNodeContents(element);

        sel.removeAllRanges();
        sel.addRange(range);
    } else if (document.body.createTextRange) {
        range = document.body.createTextRange();
        range.moveToElementText(element);
        range.select();
    }
}

function should_list_all_streams() {
    return !page_params.realm_is_zephyr_mirror_realm;
}

// this finds the stream that is actively open in the settings and focused in
// the left side.
exports.active_stream = function () {
    const hash_components = window.location.hash.substr(1).split(/\//);

    // if the string casted to a number is valid, and another component
    // after exists then it's a stream name/id pair.
    if (typeof parseFloat(hash_components[1]) === "number" && hash_components[2]) {
        return {
            id: parseFloat(hash_components[1]),
            name: hash_components[2],
        };
    }
};

exports.set_muted = function (sub, is_muted, status_element) {
    stream_muting.update_is_muted(sub, is_muted);
    stream_edit.set_stream_property(sub, "is_muted", sub.is_muted, status_element);
};

exports.toggle_pin_to_top_stream = function (sub) {
    stream_edit.set_stream_property(sub, "pin_to_top", !sub.pin_to_top);
};

let subscribed_only = true;

exports.is_subscribed_stream_tab_active = function () {
    // Returns true if "Subscribed" tab in stream settings is open
    // otherwise false.
    return subscribed_only;
};

exports.update_stream_name = function (sub, new_name) {
    const old_name = sub.name;

    // Rename the stream internally.
    stream_data.rename_sub(sub, new_name);
    const stream_id = sub.stream_id;

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the stream settings
    stream_edit.update_stream_name(sub, new_name);

    // Update the subscriptions page
    const sub_row = exports.row_for_stream_id(stream_id);
    sub_row.find(".stream-name").text(new_name);

    // Update the message feed.
    message_live_update.update_stream_name(stream_id, new_name);

    // Clear rendered typeahead cache
    typeahead_helper.clear_rendered_stream(stream_id);

    // Update compose_state if needed
    if (compose_state.stream_name() === old_name) {
        compose_state.stream_name(new_name);
    }

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
};

exports.update_stream_description = function (sub, description, rendered_description) {
    sub.description = description;
    sub.rendered_description = rendered_description.replace("<p>", "").replace("</p>", "");

    // Update stream row
    const sub_row = exports.row_for_stream_id(sub.stream_id);
    sub_row.find(".description").html(util.clean_user_content_links(sub.rendered_description));

    // Update stream settings
    stream_edit.update_stream_description(sub);

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
};

exports.update_stream_privacy = function (sub, values) {
    stream_data.update_stream_privacy(sub, values);
    stream_data.update_calculated_fields(sub);

    // Update UI elements
    stream_ui_updates.update_stream_privacy_type_icon(sub);
    stream_ui_updates.update_stream_subscription_type_text(sub);
    stream_ui_updates.update_change_stream_privacy_settings(sub);
    stream_ui_updates.update_settings_button_for_sub(sub);
    stream_ui_updates.update_subscribers_count(sub);
    stream_ui_updates.update_add_subscriptions_elements(sub);
    stream_list.redraw_stream_privacy(sub);

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
};

exports.update_stream_post_policy = function (sub, new_value) {
    stream_data.update_stream_post_policy(sub, new_value);
    stream_data.update_calculated_fields(sub);

    stream_ui_updates.update_stream_subscription_type_text(sub);
};

exports.update_message_retention_setting = function (sub, new_value) {
    stream_data.update_message_retention_setting(sub, new_value);
    stream_ui_updates.update_stream_subscription_type_text(sub);
};

exports.set_color = function (stream_id, color) {
    const sub = stream_data.get_sub_by_id(stream_id);
    stream_edit.set_stream_property(sub, "color", color);
};

exports.rerender_subscriptions_settings = function (sub) {
    // This rerendes the subscriber data for a given sub object
    // where it might have already been rendered in the subscriptions UI.
    if (typeof sub === "undefined") {
        blueslip.error("Undefined sub passed to function rerender_subscriptions_settings");
        return;
    }
    stream_data.update_subscribers_count(sub);
    stream_ui_updates.update_subscribers_count(sub);
    stream_ui_updates.update_subscribers_list(sub);
};

exports.update_subscribers_ui = function (sub) {
    // We rely on rerender_subscriptions_settings to complete the
    // stream_data subscribers count update
    exports.rerender_subscriptions_settings(sub);
    message_view_header.maybe_rerender_title_area_for_stream(sub);
};

exports.add_sub_to_table = function (sub) {
    if (exports.is_sub_already_present(sub)) {
        // If a stream is already listed/added in subscription modal,
        // display stream in `Subscribed` tab and return.
        // This can happen in some corner cases (which might
        // be backend bugs) where a realm adminsitrator is subscribed
        // to a private stream, in which case they might get two
        // stream-create events.
        stream_ui_updates.update_stream_row_in_settings_tab(sub);
        return;
    }

    const html = render_subscription(sub);
    const settings_html = render_subscription_settings(sub);
    if (stream_create.get_name() === sub.name) {
        ui.get_content_element($(".streams-list")).prepend(html);
        ui.reset_scrollbar($(".streams-list"));
    } else {
        ui.get_content_element($(".streams-list")).append(html);
    }
    ui.get_content_element($(".subscriptions .settings")).append($(settings_html));

    if (stream_create.get_name() === sub.name) {
        // This `stream_create.get_name()` check tells us whether the
        // stream was just created in this browser window; it's a hack
        // to work around the server_events code flow not having a
        // good way to associate with this request because the stream
        // ID isn't known yet.  These are appended to the top of the
        // list, so they are more visible.
        exports.row_for_stream_id(sub.stream_id).trigger("click");
        stream_create.reset_created_stream();
    }
};

exports.is_sub_already_present = function (sub) {
    // This checks if a stream is already listed the "Manage streams"
    // UI, by checking for its subscribe/unsubscribe checkmark button.
    const button = exports.check_button_for_sub(sub);
    if (button.length !== 0) {
        return true;
    }
    return false;
};

exports.remove_stream = function (stream_id) {
    // It is possible that row is empty when we deactivate a
    // stream, but we let jQuery silently handle that.
    const row = exports.row_for_stream_id(stream_id);
    row.remove();
    const sub = stream_data.get_sub_by_id(stream_id);
    if (stream_edit.is_sub_settings_active(sub)) {
        stream_edit.open_edit_panel_empty();
    }
};

exports.update_settings_for_subscribed = function (sub) {
    stream_ui_updates.update_add_subscriptions_elements(sub);
    $(
        ".subscription_settings[data-stream-id='" + sub.stream_id + "'] #preview-stream-button",
    ).show();

    if (exports.is_sub_already_present(sub)) {
        stream_data.update_subscribers_count(sub);
        stream_ui_updates.update_stream_row_in_settings_tab(sub);
        stream_ui_updates.update_subscribers_count(sub, true);
        stream_ui_updates.update_check_button_for_sub(sub);
        stream_ui_updates.update_settings_button_for_sub(sub);
        stream_ui_updates.update_change_stream_privacy_settings(sub);
    } else {
        exports.add_sub_to_table(sub);
    }

    stream_ui_updates.update_subscribers_list(sub);

    // Display the swatch and subscription stream_settings
    stream_ui_updates.update_regular_sub_settings(sub);
};

exports.show_active_stream_in_left_panel = function () {
    const selected_row = get_hash_safe().split(/\//)[1];

    if (parseFloat(selected_row)) {
        const sub_row = exports.row_for_stream_id(selected_row);
        sub_row.addClass("active");
    }
};

exports.add_tooltips_to_left_panel = function () {
    for (const row of $("#subscriptions_table .stream-row")) {
        $(row).find('.sub-info-box [class$="-bar"] [class$="-count"]').tooltip({
            placement: "left",
            animation: false,
        });
    }
};

exports.update_settings_for_unsubscribed = function (sub) {
    exports.rerender_subscriptions_settings(sub);
    stream_ui_updates.update_check_button_for_sub(sub);
    stream_ui_updates.update_settings_button_for_sub(sub);
    stream_ui_updates.update_regular_sub_settings(sub);
    stream_ui_updates.update_change_stream_privacy_settings(sub);

    stream_data.update_stream_email_address(sub, "");
    // If user unsubscribed from private stream then user cannot subscribe to
    // stream without invitation and cannot add subscribers to stream.
    if (!sub.should_display_subscription_button) {
        stream_ui_updates.update_add_subscriptions_elements(sub);
    }
    if (page_params.is_guest) {
        stream_edit.open_edit_panel_empty();
    }

    // Remove private streams from subscribed streams list.
    stream_ui_updates.update_stream_row_in_settings_tab(sub);
};

function triage_stream(query, sub) {
    if (query.subscribed_only) {
        // reject non-subscribed streams
        if (!sub.subscribed) {
            return "rejected";
        }
    }

    const search_terms = search_util.get_search_terms(query.input);

    function match(attr) {
        const val = sub[attr];

        return search_util.vanilla_match({
            val,
            search_terms,
        });
    }

    if (match("name")) {
        return "name_match";
    }

    if (match("description")) {
        return "desc_match";
    }

    return "rejected";
}

function get_stream_id_buckets(stream_ids, query) {
    // When we simplify the settings UI, we can get
    // rid of the "others" bucket.

    const buckets = {
        name: [],
        desc: [],
        other: [],
    };

    for (const stream_id of stream_ids) {
        const sub = stream_data.get_sub_by_id(stream_id);
        const match_status = triage_stream(query, sub);

        if (match_status === "name_match") {
            buckets.name.push(stream_id);
        } else if (match_status === "desc_match") {
            buckets.desc.push(stream_id);
        } else {
            buckets.other.push(stream_id);
        }
    }

    stream_data.sort_for_stream_settings(buckets.name, query.sort_order);
    stream_data.sort_for_stream_settings(buckets.desc, query.sort_order);

    return buckets;
}

exports.populate_stream_settings_left_panel = function () {
    const sub_rows = stream_data.get_updated_unsorted_subs();

    const template_data = {
        subscriptions: sub_rows,
    };

    const finish = blueslip.start_timing("render_subscriptions");
    const html = render_subscriptions(template_data);
    finish();

    ui.get_content_element($("#subscriptions_table .streams-list")).html(html);
};

// query is now an object rather than a string.
// Query { input: String, subscribed_only: Boolean, sort_order: String }
exports.filter_table = function (query) {
    exports.show_active_stream_in_left_panel();

    function stream_id_for_row(row) {
        return parseInt($(row).attr("data-stream-id"), 10);
    }

    const widgets = new Map();
    const streams_list_scrolltop = ui.get_scroll_element($(".streams-list")).scrollTop();

    const stream_ids = [];

    for (const row of $("#subscriptions_table .stream-row")) {
        const stream_id = stream_id_for_row(row);
        stream_ids.push(stream_id);
    }

    const buckets = get_stream_id_buckets(stream_ids, query);

    // If we just re-built the DOM from scratch we wouldn't need
    // all this hidden/notdisplayed logic.
    const hidden_ids = new Set();

    for (const stream_id of buckets.other) {
        hidden_ids.add(stream_id);
    }

    for (const row of $("#subscriptions_table .stream-row")) {
        const stream_id = stream_id_for_row(row);

        // Below code goes away if we don't do sort-DOM-in-place.
        if (hidden_ids.has(stream_id)) {
            $(row).addClass("notdisplayed");
        } else {
            $(row).removeClass("notdisplayed");
        }

        widgets.set(stream_id, $(row).detach());
    }

    exports.add_tooltips_to_left_panel();

    ui.reset_scrollbar($("#subscription_overlay .streams-list"));

    const all_stream_ids = [...buckets.name, ...buckets.desc, ...buckets.other];

    for (const stream_id of all_stream_ids) {
        ui.get_content_element($("#subscriptions_table .streams-list")).append(
            widgets.get(stream_id),
        );
    }

    exports.maybe_reset_right_panel();

    // this puts the scrollTop back to what it was before the list was updated again.
    ui.get_scroll_element($(".streams-list")).scrollTop(streams_list_scrolltop);
};

let sort_order = "by-stream-name";

exports.get_search_params = function () {
    const search_box = $("#stream_filter input[type='text']");
    const input = search_box.expectOne().val().trim();
    const params = {
        input,
        subscribed_only,
        sort_order,
    };
    return params;
};

exports.maybe_reset_right_panel = function () {
    if ($(".stream-row.active").hasClass("notdisplayed")) {
        $(".right .settings").hide();
        $(".nothing-selected").show();
        $(".stream-row.active").removeClass("active");
    }
};

exports.actually_filter_streams = function () {
    const search_params = exports.get_search_params();
    exports.filter_table(search_params);
};

const filter_streams = _.throttle(exports.actually_filter_streams, 50);

// Make it explicit that our toggler is not created right away.
exports.toggler = undefined;

exports.switch_stream_tab = function (tab_name) {
    /*
        This switches the stream tab, but it doesn't update
        the toggler widget.  You may instead want to
        use `toggler.goto`.
    */

    if (tab_name === "all-streams") {
        subscribed_only = false;
    } else if (tab_name === "subscribed") {
        subscribed_only = true;
    }

    exports.actually_filter_streams();
    stream_edit.setup_subscriptions_tab_hash(tab_name);
};

exports.sort_toggler = undefined;
exports.switch_stream_sort = function (tab_name) {
    if (
        tab_name === "by-stream-name" ||
        tab_name === "by-subscriber-count" ||
        tab_name === "by-weekly-traffic"
    ) {
        sort_order = tab_name;
    } else {
        sort_order = "by-stream-name";
    }
    exports.actually_filter_streams();
};

exports.setup_page = function (callback) {
    // We should strongly consider only setting up the page once,
    // but I am writing these comments write before a big release,
    // so it's too risky a change for now.
    //
    // The history behind setting up the page from scratch every
    // time we go into "Manage Streams" is that we used to have
    // some live-update issues, so being able to re-launch the
    // streams page is kind of a workaround for those bugs, since
    // we will re-populate the widget.
    //
    // For now, every time we go back into the widget we'll
    // continue the strategy that we re-render everything from scratch.
    // Also, we'll always go back to the "Subscribed" tab.
    function initialize_components() {
        // Sort by name by default when opening "Manage streams".
        sort_order = "by-stream-name";
        exports.sort_toggler = components.toggle({
            values: [
                {
                    label: `<i class="fa fa-sort-alpha-asc" title="${i18n.t("Sort by name")}"></i>`,
                    key: "by-stream-name",
                },
                {
                    label: `<i class="fa fa-user-o" title="${i18n.t(
                        "Sort by number of subscribers",
                    )}"></i>`,
                    key: "by-subscriber-count",
                },
                {
                    label: `<i class="fa fa-bar-chart" title="${i18n.t(
                        "Sort by estimated weekly traffic",
                    )}"></i>`,
                    key: "by-weekly-traffic",
                },
            ],
            html_class: "stream_sorter_toggle",
            callback(value, key) {
                exports.switch_stream_sort(key);
            },
        });
        $("#subscriptions_table .search-container").prepend(exports.sort_toggler.get());

        // Reset our internal state to reflect that we're initially in
        // the "Subscribed" tab if we're reopening "Manage streams".
        subscribed_only = true;
        exports.toggler = components.toggle({
            child_wants_focus: true,
            values: [
                {label: i18n.t("Subscribed"), key: "subscribed"},
                {label: i18n.t("All streams"), key: "all-streams"},
            ],
            callback(value, key) {
                exports.switch_stream_tab(key);
            },
        });

        if (should_list_all_streams()) {
            const toggler_elem = exports.toggler.get();
            $("#subscriptions_table .search-container").prepend(toggler_elem);
        }
        if (page_params.is_guest) {
            exports.toggler.disable_tab("all-streams");
        }

        // show the "Stream settings" header by default.
        $(".display-type #stream_settings_title").show();
    }

    function populate_and_fill() {
        $("#subscriptions_table").empty();

        const template_data = {
            can_create_streams: page_params.can_create_streams,
            hide_all_streams: !should_list_all_streams(),
            max_name_length: page_params.stream_name_max_length,
            max_description_length: page_params.stream_description_max_length,
            is_owner: page_params.is_owner,
            stream_privacy_policy_values: stream_data.stream_privacy_policy_values,
            stream_post_policy_values: stream_data.stream_post_policy_values,
            zulip_plan_is_not_limited: page_params.zulip_plan_is_not_limited,
            realm_message_retention_setting:
                stream_edit.get_display_text_for_realm_message_retention_setting,
            upgrade_text_for_wide_organization_logo:
                page_params.upgrade_text_for_wide_organization_logo,
        };

        const rendered = render_subscription_table_body(template_data);
        $("#subscriptions_table").append(rendered);

        exports.populate_stream_settings_left_panel();
        initialize_components();
        exports.actually_filter_streams();
        stream_create.set_up_handlers();

        $("#stream_filter input[type='text']").on("input", () => {
            // Debounce filtering in case a user is typing quickly
            filter_streams();
        });

        $("#clear_search_stream_name").on("click", () => {
            $("#stream_filter input[type='text']").val("");
            filter_streams();
        });

        if (callback) {
            callback();
        }
    }

    populate_and_fill();

    if (!should_list_all_streams()) {
        $(".create_stream_button").val(i18n.t("Subscribe"));
    }
};

exports.switch_to_stream_row = function (stream_id) {
    const stream_row = exports.row_for_stream_id(stream_id);
    const container = $(".streams-list");

    exports.get_active_data().row.removeClass("active");
    stream_row.addClass("active");

    scroll_util.scroll_element_into_container(stream_row, container);

    // It's dubious that we need this timeout any more.
    setTimeout(() => {
        if (stream_id === exports.get_active_data().id) {
            stream_row.trigger("click");
        }
    }, 100);
};

exports.change_state = function (section) {
    // if in #streams/new form.
    if (section === "new") {
        if (!page_params.is_guest) {
            exports.do_open_create_stream();
        } else {
            exports.toggler.goto("subscribed");
        }
        return;
    }

    if (section === "all") {
        exports.toggler.goto("all-streams");
        return;
    }

    if (section === "subscribed") {
        exports.toggler.goto("subscribed");
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        const stream_id = parseInt(section, 10);
        // Guest users can not access unsubscribed streams
        // So redirect guest users to 'subscribed' tab
        // for any unsubscribed stream settings hash
        if (page_params.is_guest && !stream_data.id_is_subscribed(stream_id)) {
            exports.toggler.goto("subscribed");
        } else {
            exports.switch_to_stream_row(stream_id);
        }
        return;
    }

    blueslip.warn("invalid section for streams: " + section);
    exports.toggler.goto("subscribed");
};

exports.launch = function (section) {
    exports.setup_page(() => {
        overlays.open_overlay({
            name: "subscriptions",
            overlay: $("#subscription_overlay"),
            on_close() {
                hashchange.exit_overlay();
            },
        });
        exports.change_state(section);
    });
    if (!exports.get_active_data().id) {
        $("#search_stream_name").trigger("focus");
    }
};

exports.switch_rows = function (event) {
    const active_data = exports.get_active_data();
    let switch_row;
    if (window.location.hash === "#streams/new") {
        // Prevent switching stream rows when creating a new stream
        return false;
    } else if (!active_data.id || active_data.row.hasClass("notdisplayed")) {
        switch_row = $("div.stream-row:not(.notdisplayed)").first();
        if ($("#search_stream_name").is(":focus")) {
            $("#search_stream_name").trigger("blur");
        }
    } else {
        if (event === "up_arrow") {
            switch_row = active_data.row.prevAll().not(".notdisplayed").first();
        } else if (event === "down_arrow") {
            switch_row = active_data.row.nextAll().not(".notdisplayed").first();
        }
        if ($("#search_stream_name").is(":focus")) {
            // remove focus from Filter streams input instead of switching rows
            // if Filter streams input is focused
            return $("#search_stream_name").trigger("blur");
        }
    }

    const row_data = get_row_data(switch_row);
    if (row_data) {
        const stream_id = row_data.id;
        exports.switch_to_stream_row(stream_id);
    } else if (event === "up_arrow" && !row_data) {
        $("#search_stream_name").trigger("focus");
    }
    return true;
};

exports.keyboard_sub = function () {
    const active_data = exports.get_active_data();
    const stream_filter_tab = $(active_data.tabs[0]).text();
    const row_data = get_row_data(active_data.row);
    if (row_data) {
        exports.sub_or_unsub(row_data.object);
        if (row_data.object.subscribed && stream_filter_tab === "Subscribed") {
            active_data.row.addClass("notdisplayed");
            active_data.row.removeClass("active");
        }
    }
};

exports.toggle_view = function (event) {
    const active_data = exports.get_active_data();
    const stream_filter_tab = $(active_data.tabs[0]).text();

    if (event === "right_arrow" && stream_filter_tab === "Subscribed") {
        exports.toggler.goto("all-streams");
    } else if (event === "left_arrow" && stream_filter_tab === "All streams") {
        exports.toggler.goto("subscribed");
    }
};

exports.view_stream = function () {
    const active_data = exports.get_active_data();
    const row_data = get_row_data(active_data.row);
    if (row_data) {
        const stream_narrow_hash =
            "#narrow/stream/" + hash_util.encode_stream_name(row_data.object.name);
        hashchange.go_to_location(stream_narrow_hash);
    }
};

/* For the given stream_row, remove the tick and replace by a spinner. */
function display_subscribe_toggle_spinner(stream_row) {
    /* Prevent sending multiple requests by removing the button class. */
    $(stream_row).find(".check").removeClass("sub_unsub_button");

    /* Hide the tick. */
    const tick = $(stream_row).find("svg");
    tick.addClass("hide");

    /* Add a spinner to show the request is in process. */
    const spinner = $(stream_row).find(".sub_unsub_status").expectOne();
    spinner.show();
    loading.make_indicator(spinner);
}

/* For the given stream_row, add the tick and delete the spinner. */
function hide_subscribe_toggle_spinner(stream_row) {
    /* Re-enable the button to handle requests. */
    $(stream_row).find(".check").addClass("sub_unsub_button");

    /* Show the tick. */
    const tick = $(stream_row).find("svg");
    tick.removeClass("hide");

    /* Destroy the spinner. */
    const spinner = $(stream_row).find(".sub_unsub_status").expectOne();
    loading.destroy_indicator(spinner);
}

function ajaxSubscribe(stream, color, stream_row) {
    // Subscribe yourself to a single stream.
    let true_stream_name;

    if (stream_row !== undefined) {
        display_subscribe_toggle_spinner(stream_row);
    }
    return channel.post({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([{name: stream, color}])},
        success(resp, statusText, xhr) {
            if (overlays.streams_open()) {
                $("#create_stream_name").val("");
            }

            const res = JSON.parse(xhr.responseText);
            if (!$.isEmptyObject(res.already_subscribed)) {
                // Display the canonical stream capitalization.
                true_stream_name = res.already_subscribed[people.my_current_email()][0];
                ui_report.success(
                    i18n.t("Already subscribed to __stream__", {stream: true_stream_name}),
                    $(".stream_change_property_info"),
                );
            }
            // The rest of the work is done via the subscribe event we will get

            if (stream_row !== undefined) {
                hide_subscribe_toggle_spinner(stream_row);
            }
        },
        error(xhr) {
            if (stream_row !== undefined) {
                hide_subscribe_toggle_spinner(stream_row);
            }
            ui_report.error(
                i18n.t("Error adding subscription"),
                xhr,
                $(".stream_change_property_info"),
            );
        },
    });
}

function ajaxUnsubscribe(sub, stream_row) {
    // TODO: use stream_id when backend supports it
    if (stream_row !== undefined) {
        display_subscribe_toggle_spinner(stream_row);
    }
    return channel.del({
        url: "/json/users/me/subscriptions",
        data: {subscriptions: JSON.stringify([sub.name])},
        success() {
            $(".stream_change_property_info").hide();
            // The rest of the work is done via the unsubscribe event we will get

            if (stream_row !== undefined) {
                hide_subscribe_toggle_spinner(stream_row);
            }
        },
        error(xhr) {
            if (stream_row !== undefined) {
                hide_subscribe_toggle_spinner(stream_row);
            }
            ui_report.error(
                i18n.t("Error removing subscription"),
                xhr,
                $(".stream_change_property_info"),
            );
        },
    });
}

exports.do_open_create_stream = function () {
    // Only call this directly for hash changes.
    // Prefer open_create_stream().

    const stream = $("#search_stream_name").val().trim();

    if (!should_list_all_streams()) {
        // Realms that don't allow listing streams should simply be subscribed to.
        stream_create.set_name(stream);
        ajaxSubscribe($("#search_stream_name").val());
        return;
    }

    stream_create.new_stream_clicked(stream);
};

exports.open_create_stream = function () {
    exports.do_open_create_stream();
    hashchange.update_browser_history("#streams/new");
};

exports.sub_or_unsub = function (sub, stream_row) {
    if (sub.subscribed) {
        ajaxUnsubscribe(sub, stream_row);
    } else {
        ajaxSubscribe(sub.name, sub.color, stream_row);
    }
};

exports.initialize = function () {
    $("#subscriptions_table").on("click", ".create_stream_button", (e) => {
        e.preventDefault();
        exports.open_create_stream();
    });

    $(".subscriptions").on("click", "[data-dismiss]", (e) => {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "Enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            exports.show_subs_pane.nothing_selected();
        }
    });

    $("#subscriptions_table").on("click", ".email-address", function () {
        selectText(this);
    });

    $("#subscriptions_table").on("click", ".stream-row, .create_stream_button", () => {
        $(".right").addClass("show");
        $(".subscriptions-header").addClass("slide-left");
    });

    $("#subscriptions_table").on("click", ".fa-chevron-left", () => {
        $(".right").removeClass("show");
        $(".subscriptions-header").removeClass("slide-left");
    });

    (function defocus_sub_settings() {
        const sel = ".search-container, .streams-list, .subscriptions-header";

        $("#subscriptions_table").on("click", sel, (e) => {
            if ($(e.target).is(sel)) {
                stream_edit.open_edit_panel_empty();
            }
        });
    })();
};

window.subs = exports;
