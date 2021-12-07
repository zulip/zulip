import $ from "jquery";
import _ from "lodash";
import tippy from "tippy.js";

import render_unsubscribe_private_stream_modal from "../templates/confirm_dialog/confirm_unsubscribe_private_stream.hbs";
import render_browse_streams_list from "../templates/stream_settings/browse_streams_list.hbs";
import render_browse_streams_list_item from "../templates/stream_settings/browse_streams_list_item.hbs";
import render_stream_settings from "../templates/stream_settings/stream_settings.hbs";
import render_stream_settings_overlay from "../templates/stream_settings/stream_settings_overlay.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as channel from "./channel";
import * as components from "./components";
import * as compose_state from "./compose_state";
import * as confirm_dialog from "./confirm_dialog";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as loading from "./loading";
import * as message_live_update from "./message_live_update";
import * as message_view_header from "./message_view_header";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as scroll_util from "./scroll_util";
import * as search_util from "./search_util";
import * as settings_data from "./settings_data";
import * as stream_create from "./stream_create";
import * as stream_data from "./stream_data";
import * as stream_edit from "./stream_edit";
import * as stream_list from "./stream_list";
import * as stream_muting from "./stream_muting";
import * as stream_settings_data from "./stream_settings_data";
import * as stream_ui_updates from "./stream_ui_updates";
import * as sub_store from "./sub_store";
import * as ui from "./ui";
import * as ui_report from "./ui_report";
import * as util from "./util";

export const show_subs_pane = {
    nothing_selected() {
        $(".settings, #stream-creation").hide();
        $(".nothing-selected").show();
        $("#subscription_overlay .stream-info-title").text($t({defaultMessage: "Stream settings"}));
    },
    settings(stream_name) {
        $(".settings, #stream-creation").hide();
        $(".settings").show();
        $("#subscription_overlay .stream-info-title").text("#" + stream_name);
    },
    create_stream() {
        $(".nothing-selected, .settings, #stream-creation").hide();
        $("#stream-creation").show();
        $("#subscription_overlay .stream-info-title").text($t({defaultMessage: "Create stream"}));
    },
};

export function row_for_stream_id(stream_id) {
    return $(`.stream-row[data-stream-id='${CSS.escape(stream_id)}']`);
}

export function is_sub_already_present(sub) {
    return row_for_stream_id(sub.stream_id).length > 0;
}

export function update_left_panel_row(sub) {
    const row = row_for_stream_id(sub.stream_id);

    if (row.length === 0) {
        return;
    }

    blueslip.debug(`Updating row in left panel of stream settings for: ${sub.name}`);
    const setting_sub = stream_settings_data.get_sub_for_settings(sub);
    const html = render_browse_streams_list_item(setting_sub);
    const new_row = $(html);

    // TODO: Clean up this hack when we eliminate `notdisplayed`
    if (row.hasClass("notdisplayed")) {
        new_row.addClass("notdisplayed");
    }

    // TODO: Remove this if/when we just handle "active" when rendering templates.
    if (row.hasClass("active")) {
        new_row.addClass("active");
    }

    row.replaceWith(new_row);
}

export function settings_button_for_sub(sub) {
    // We don't do expectOne() here, because this button is only
    // visible if the user has that stream selected in the streams UI.
    return $(
        `.stream_settings_header[data-stream-id='${CSS.escape(sub.stream_id)}'] .subscribe-button`,
    );
}

function get_row_data(row) {
    const row_id = Number.parseInt(row.attr("data-stream-id"), 10);
    if (row_id) {
        const row_object = sub_store.get(row_id);
        return {
            id: row_id,
            object: row_object,
        };
    }
    return undefined;
}

export function get_active_data() {
    const active_row = $("div.stream-row.active");
    const valid_active_id = Number.parseInt(active_row.attr("data-stream-id"), 10);
    const active_tabs = $(".subscriptions-container").find("div.ind-tab.selected");
    return {
        row: active_row,
        id: valid_active_id,
        tabs: active_tabs,
    };
}

function selectText(element) {
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(element);

    sel.removeAllRanges();
    sel.addRange(range);
}

function should_list_all_streams() {
    return !page_params.realm_is_zephyr_mirror_realm;
}

export function set_muted(sub, is_muted, status_element) {
    stream_muting.update_is_muted(sub, is_muted);
    stream_edit.set_stream_property(sub, "is_muted", sub.is_muted, status_element);
}

export function toggle_pin_to_top_stream(sub) {
    stream_edit.set_stream_property(sub, "pin_to_top", !sub.pin_to_top);
}

let subscribed_only = true;

export function is_subscribed_stream_tab_active() {
    // Returns true if "Subscribed" tab in stream settings is open
    // otherwise false.
    return subscribed_only;
}

export function update_stream_name(sub, new_name) {
    const old_name = sub.name;

    // Rename the stream internally.
    stream_data.rename_sub(sub, new_name);
    const stream_id = sub.stream_id;

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the stream settings
    stream_edit.update_stream_name(sub, new_name);

    // Update the subscriptions page
    const sub_row = row_for_stream_id(stream_id);
    sub_row.find(".stream-name").text(new_name);

    // Update the message feed.
    message_live_update.update_stream_name(stream_id, new_name);

    // Update compose_state if needed
    if (compose_state.stream_name() === old_name) {
        compose_state.stream_name(new_name);
    }

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function update_stream_description(sub, description, rendered_description) {
    sub.description = description;
    sub.rendered_description = rendered_description;
    stream_data.clean_up_description(sub);

    // Update stream row
    const sub_row = row_for_stream_id(sub.stream_id);
    sub_row.find(".description").html(util.clean_user_content_links(sub.rendered_description));

    // Update stream settings
    stream_edit.update_stream_description(sub);

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function update_stream_privacy(slim_sub, values) {
    stream_data.update_stream_privacy(slim_sub, values);
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);

    // Update UI elements
    update_left_panel_row(sub);
    stream_ui_updates.update_stream_subscription_type_text(sub);
    stream_ui_updates.update_change_stream_privacy_settings(sub);
    stream_ui_updates.update_settings_button_for_sub(sub);
    stream_ui_updates.update_add_subscriptions_elements(sub);
    stream_list.redraw_stream_privacy(sub);

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function update_stream_post_policy(sub, new_value) {
    stream_data.update_stream_post_policy(sub, new_value);
    stream_ui_updates.update_stream_subscription_type_text(sub);
}

export function update_message_retention_setting(sub, new_value) {
    stream_data.update_message_retention_setting(sub, new_value);
    stream_ui_updates.update_stream_subscription_type_text(sub);
}

export function set_color(stream_id, color) {
    const sub = sub_store.get(stream_id);
    stream_edit.set_stream_property(sub, "color", color);
}

export function update_subscribers_ui(sub) {
    update_left_panel_row(sub);
    stream_ui_updates.update_subscribers_list(sub);
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function add_sub_to_table(sub) {
    if (is_sub_already_present(sub)) {
        // If a stream is already listed/added in subscription modal,
        // display stream in `Subscribed` tab and return.
        // This can happen in some corner cases (which might
        // be backend bugs) where a realm adminsitrator is subscribed
        // to a private stream, in which case they might get two
        // stream-create events.
        stream_ui_updates.update_stream_row_in_settings_tab(sub);
        return;
    }

    const setting_sub = stream_settings_data.get_sub_for_settings(sub);
    const html = render_browse_streams_list_item(setting_sub);
    const new_row = $(html);

    if (stream_create.get_name() === sub.name) {
        ui.get_content_element($(".streams-list")).prepend(new_row);
        ui.reset_scrollbar($(".streams-list"));
    } else {
        ui.get_content_element($(".streams-list")).append(new_row);
    }

    const settings_html = render_stream_settings(sub);
    ui.get_content_element($(".subscriptions .settings")).append($(settings_html));

    if (stream_create.get_name() === sub.name) {
        // This `stream_create.get_name()` check tells us whether the
        // stream was just created in this browser window; it's a hack
        // to work around the server_events code flow not having a
        // good way to associate with this request because the stream
        // ID isn't known yet.  These are appended to the top of the
        // list, so they are more visible.
        row_for_stream_id(sub.stream_id).trigger("click");
        stream_create.reset_created_stream();
    }
}

export function remove_stream(stream_id) {
    // It is possible that row is empty when we deactivate a
    // stream, but we let jQuery silently handle that.
    const row = row_for_stream_id(stream_id);
    row.remove();
    const sub = sub_store.get(stream_id);
    if (stream_edit.is_sub_settings_active(sub)) {
        stream_edit.open_edit_panel_empty();
    }
}

export function update_settings_for_subscribed(slim_sub) {
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    stream_ui_updates.update_add_subscriptions_elements(sub);
    $(
        `.subscription_settings[data-stream-id='${CSS.escape(
            sub.stream_id,
        )}'] #preview-stream-button`,
    ).show();

    if (is_sub_already_present(sub)) {
        update_left_panel_row(sub);
        stream_ui_updates.update_toggler_for_sub(sub);
        stream_ui_updates.update_stream_row_in_settings_tab(sub);
        stream_ui_updates.update_settings_button_for_sub(sub);
        stream_ui_updates.update_change_stream_privacy_settings(sub);
    } else {
        add_sub_to_table(sub);
    }

    stream_ui_updates.update_subscribers_list(sub);

    // Display the swatch and subscription stream_settings
    stream_ui_updates.update_regular_sub_settings(sub);
}

export function show_active_stream_in_left_panel() {
    const selected_row = hash_util.get_current_hash_section();

    if (Number.parseFloat(selected_row)) {
        const sub_row = row_for_stream_id(selected_row);
        sub_row.addClass("active");
    }
}

export function update_settings_for_unsubscribed(slim_sub) {
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    update_left_panel_row(sub);
    stream_ui_updates.update_subscribers_list(sub);
    stream_ui_updates.update_toggler_for_sub(sub);
    stream_ui_updates.update_settings_button_for_sub(sub);
    stream_ui_updates.update_regular_sub_settings(sub);
    stream_ui_updates.update_change_stream_privacy_settings(sub);

    stream_data.update_stream_email_address(sub, "");
    // If user unsubscribed from private stream then user cannot subscribe to
    // stream without invitation and cannot add subscribers to stream.
    if (!stream_data.can_toggle_subscription(sub)) {
        stream_ui_updates.update_add_subscriptions_elements(sub);
    }
    if (page_params.is_guest) {
        stream_edit.open_edit_panel_empty();
    }

    // Remove private streams from subscribed streams list.
    stream_ui_updates.update_stream_row_in_settings_tab(sub);
}

function triage_stream(left_panel_params, sub) {
    if (left_panel_params.subscribed_only && !sub.subscribed) {
        // reject non-subscribed streams
        return "rejected";
    }

    const search_terms = search_util.get_search_terms(left_panel_params.input);

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

function get_stream_id_buckets(stream_ids, left_panel_params) {
    // When we simplify the settings UI, we can get
    // rid of the "others" bucket.

    const buckets = {
        name: [],
        desc: [],
        other: [],
    };

    for (const stream_id of stream_ids) {
        const sub = sub_store.get(stream_id);
        const match_status = triage_stream(left_panel_params, sub);

        if (match_status === "name_match") {
            buckets.name.push(stream_id);
        } else if (match_status === "desc_match") {
            buckets.desc.push(stream_id);
        } else {
            buckets.other.push(stream_id);
        }
    }

    stream_settings_data.sort_for_stream_settings(buckets.name, left_panel_params.sort_order);
    stream_settings_data.sort_for_stream_settings(buckets.desc, left_panel_params.sort_order);

    return buckets;
}

export function render_left_panel_superset() {
    // For annoying legacy reasons we render all the subs we are
    // allowed to know about and put them in the DOM, then we do
    // a second pass where we filter/sort them.
    const html = blueslip.measure_time("render left panel", () => {
        const sub_rows = stream_settings_data.get_updated_unsorted_subs();

        const template_data = {
            subscriptions: sub_rows,
        };

        return render_browse_streams_list(template_data);
    });

    ui.get_content_element($("#subscriptions_table .streams-list")).html(html);
}

// LeftPanelParams { input: String, subscribed_only: Boolean, sort_order: String }
export function redraw_left_panel(left_panel_params = get_left_panel_params()) {
    // We only get left_panel_params passed in from tests.  Real
    // code calls get_left_panel_params().
    show_active_stream_in_left_panel();

    function stream_id_for_row(row) {
        return Number.parseInt($(row).attr("data-stream-id"), 10);
    }

    const widgets = new Map();

    const stream_ids = [];

    for (const row of $("#subscriptions_table .stream-row")) {
        const stream_id = stream_id_for_row(row);
        stream_ids.push(stream_id);
    }

    const buckets = get_stream_id_buckets(stream_ids, left_panel_params);

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

    ui.reset_scrollbar($("#subscription_overlay .streams-list"));

    const all_stream_ids = [...buckets.name, ...buckets.desc, ...buckets.other];

    for (const stream_id of all_stream_ids) {
        ui.get_content_element($("#subscriptions_table .streams-list")).append(
            widgets.get(stream_id),
        );
    }
    maybe_reset_right_panel();

    // return this for test convenience
    return [...buckets.name, ...buckets.desc];
}

let sort_order = "by-stream-name";

export function get_left_panel_params() {
    const search_box = $("#stream_filter input[type='text']");
    const input = search_box.expectOne().val().trim();
    const params = {
        input,
        subscribed_only,
        sort_order,
    };
    return params;
}

export function maybe_reset_right_panel() {
    if ($(".stream-row.active").hasClass("notdisplayed")) {
        $(".right .settings").hide();
        $(".nothing-selected").show();
        $(".stream-row.active").removeClass("active");
    }
}

// Make it explicit that our toggler is not created right away.
export let toggler;

export function switch_stream_tab(tab_name) {
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

    redraw_left_panel();
    stream_edit.setup_subscriptions_tab_hash(tab_name);
}

export function switch_stream_sort(tab_name) {
    if (
        tab_name === "by-stream-name" ||
        tab_name === "by-subscriber-count" ||
        tab_name === "by-weekly-traffic"
    ) {
        sort_order = tab_name;
    } else {
        sort_order = "by-stream-name";
    }
    redraw_left_panel();
}

export function setup_page(callback) {
    // We should strongly consider only setting up the page once,
    // but I am writing these comments write before a big release,
    // so it's too risky a change for now.
    //
    // The history behind setting up the page from scratch every
    // time we go into "Manage streams" is that we used to have
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
        const sort_toggler = components.toggle({
            values: [
                {
                    label_html: `<i class="fa fa-sort-alpha-asc tippy-bottom tippy-zulip-tooltip" data-tippy-content="${$t(
                        {defaultMessage: "Sort by name"},
                    )}"></i>`,
                    key: "by-stream-name",
                },
                {
                    label_html: `<i class="fa fa-user-o tippy-bottom tippy-zulip-tooltip" data-tippy-content="${$t(
                        {defaultMessage: "Sort by number of subscribers"},
                    )}"></i>`,
                    key: "by-subscriber-count",
                },
                {
                    label_html: `<i class="fa fa-bar-chart tippy-bottom tippy-zulip-tooltip" data-tippy-content="${$t(
                        {defaultMessage: "Sort by estimated weekly traffic"},
                    )}"></i>`,
                    key: "by-weekly-traffic",
                },
            ],
            html_class: "stream_sorter_toggle",
            callback(value, key) {
                switch_stream_sort(key);
            },
        });
        $("#subscriptions_table .search-container").prepend(sort_toggler.get());

        // place subs tooltips at bottom
        tippy(".tippy-bottom", {
            placement: "bottom",
        });

        // Reset our internal state to reflect that we're initially in
        // the "Subscribed" tab if we're reopening "Manage streams".
        subscribed_only = true;
        toggler = components.toggle({
            child_wants_focus: true,
            values: [
                {label: $t({defaultMessage: "Subscribed"}), key: "subscribed"},
                {label: $t({defaultMessage: "All streams"}), key: "all-streams"},
            ],
            callback(value, key) {
                switch_stream_tab(key);
            },
        });

        if (should_list_all_streams()) {
            const toggler_elem = toggler.get();
            $("#subscriptions_table .search-container").prepend(toggler_elem);
        }
        if (page_params.is_guest) {
            toggler.disable_tab("all-streams");
        }

        // show the "Stream settings" header by default.
        $(".display-type #stream_settings_title").show();
    }

    function populate_and_fill() {
        $("#subscriptions_table").empty();

        // TODO: Ideally we'd indicate in some way what stream types
        // the user can create, by showing other options as disabled.
        const stream_privacy_policy = stream_data.stream_privacy_policy_values.public.code;
        const template_data = {
            can_create_streams:
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams(),
            hide_all_streams: !should_list_all_streams(),
            max_name_length: page_params.max_stream_name_length,
            max_description_length: page_params.max_stream_description_length,
            is_owner: page_params.is_owner,
            stream_privacy_policy_values: stream_data.stream_privacy_policy_values,
            stream_privacy_policy,
            stream_post_policy_values: stream_data.stream_post_policy_values,
            zulip_plan_is_not_limited: page_params.zulip_plan_is_not_limited,
            org_level_message_retention_setting:
                stream_edit.get_display_text_for_realm_message_retention_setting(),
            upgrade_text_for_wide_organization_logo:
                page_params.upgrade_text_for_wide_organization_logo,
            disable_message_retention_setting:
                !page_params.zulip_plan_is_not_limited || !page_params.is_owner,
        };

        const rendered = render_stream_settings_overlay(template_data);
        $("#subscriptions_table").append(rendered);

        render_left_panel_superset();
        initialize_components();
        redraw_left_panel();
        stream_create.set_up_handlers();

        const throttled_redraw_left_panel = _.throttle(redraw_left_panel, 50);
        $("#stream_filter input[type='text']").on("input", () => {
            // Debounce filtering in case a user is typing quickly
            throttled_redraw_left_panel();
        });

        // When hitting Enter in the stream creation box, we open the
        // "create stream" UI with the stream name prepopulated.  This
        // is only useful if the user has permission to create
        // streams, either explicitly via user_can_create_streams, or
        // implicitly because page_params.realm_is_zephyr_mirror_realm.
        $("#stream_filter input[type='text']").on("keypress", (e) => {
            if (e.key !== "Enter") {
                return;
            }

            if (
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                page_params.realm_is_zephyr_mirror_realm
            ) {
                open_create_stream();
                e.preventDefault();
                e.stopPropagation();
                return;
            }
        });

        $("#clear_search_stream_name").on("click", () => {
            $("#stream_filter input[type='text']").val("");
            redraw_left_panel();
        });

        if (callback) {
            callback();
        }
    }

    populate_and_fill();

    if (!should_list_all_streams()) {
        $(".create_stream_button").val($t({defaultMessage: "Subscribe"}));
    }
}

export function switch_to_stream_row(stream_id) {
    const stream_row = row_for_stream_id(stream_id);
    const container = $(".streams-list");

    get_active_data().row.removeClass("active");
    stream_row.addClass("active");

    scroll_util.scroll_element_into_container(stream_row, container);

    // It's dubious that we need this timeout any more.
    setTimeout(() => {
        if (stream_id === get_active_data().id) {
            stream_row.trigger("click");
        }
    }, 100);
}

function show_right_section() {
    $(".right").addClass("show");
    $(".subscriptions-header").addClass("slide-left");
}

export function change_state(section) {
    // if in #streams/new form.
    if (section === "new") {
        if (!page_params.is_guest) {
            do_open_create_stream();
            show_right_section();
        } else {
            toggler.goto("subscribed");
        }
        return;
    }

    if (section === "all") {
        toggler.goto("all-streams");
        return;
    }

    if (section === "subscribed") {
        toggler.goto("subscribed");
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        const stream_id = Number.parseInt(section, 10);
        // Guest users can not access unsubscribed streams
        // So redirect guest users to 'subscribed' tab
        // for any unsubscribed stream settings hash
        if (page_params.is_guest && !stream_data.id_is_subscribed(stream_id)) {
            toggler.goto("subscribed");
        } else {
            show_right_section();
            switch_to_stream_row(stream_id);
        }
        return;
    }

    blueslip.warn("invalid section for streams: " + section);
    toggler.goto("subscribed");
}

export function launch(section) {
    setup_page(() => {
        overlays.open_overlay({
            name: "subscriptions",
            overlay: $("#subscription_overlay"),
            on_close() {
                browser_history.exit_overlay();
                $(".colorpicker").spectrum("destroy");
            },
        });
        change_state(section);
    });
    if (!get_active_data().id) {
        if (section === "new") {
            $("#create_stream_name").trigger("focus");
        } else {
            $("#search_stream_name").trigger("focus");
        }
    }
}

export function switch_rows(event) {
    const active_data = get_active_data();
    let switch_row;
    if (hash_util.is_create_new_stream_narrow()) {
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
        switch_to_stream_row(stream_id);
    } else if (event === "up_arrow" && !row_data) {
        $("#search_stream_name").trigger("focus");
    }
    return true;
}

export function keyboard_sub() {
    const active_data = get_active_data();
    const row_data = get_row_data(active_data.row);
    if (row_data) {
        sub_or_unsub(row_data.object);
    }
}

export function toggle_view(event) {
    const active_data = get_active_data();
    const stream_filter_tab = $(active_data.tabs[0]).text();

    if (event === "right_arrow" && stream_filter_tab === "Subscribed") {
        toggler.goto("all-streams");
    } else if (event === "left_arrow" && stream_filter_tab === "All streams") {
        toggler.goto("subscribed");
    }
}

export function view_stream() {
    const active_data = get_active_data();
    const row_data = get_row_data(active_data.row);
    if (row_data) {
        const stream_narrow_hash =
            "#narrow/stream/" + hash_util.encode_stream_name(row_data.object.name);
        browser_history.go_to_location(stream_narrow_hash);
    }
}

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
                    $t_html(
                        {defaultMessage: "Already subscribed to {stream}"},
                        {stream: true_stream_name},
                    ),
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
                $t_html({defaultMessage: "Error adding subscription"}),
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
                $t_html({defaultMessage: "Error removing subscription"}),
                xhr,
                $(".stream_change_property_info"),
            );
        },
    });
}

export function do_open_create_stream() {
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
}

export function open_create_stream() {
    do_open_create_stream();
    browser_history.update("#streams/new");
}

export function unsubscribe_from_private_stream(sub) {
    const html_body = render_unsubscribe_private_stream_modal();

    function unsubscribe_from_stream() {
        let stream_row;
        if (overlays.streams_open()) {
            stream_row = $(
                "#subscriptions_table div.stream-row[data-stream-id='" + sub.stream_id + "']",
            );
        }

        ajaxUnsubscribe(sub, stream_row);
    }

    confirm_dialog.launch({
        html_heading: $t_html(
            {defaultMessage: "Unsubscribe from {stream_name}"},
            {stream_name: sub.name},
        ),
        html_body,
        on_click: unsubscribe_from_stream,
    });
}

export function sub_or_unsub(sub, stream_row) {
    if (sub.subscribed) {
        // TODO: This next line should allow guests to access web-public streams.
        if (sub.invite_only || page_params.is_guest) {
            unsubscribe_from_private_stream(sub);
            return;
        }
        ajaxUnsubscribe(sub, stream_row);
    } else {
        ajaxSubscribe(sub.name, sub.color, stream_row);
    }
}

export function initialize() {
    $("#subscriptions_table").on("click", ".create_stream_button", (e) => {
        e.preventDefault();
        open_create_stream();
    });

    $(".subscriptions").on("click", "#stream_creation_form [data-dismiss]", (e) => {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "Enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            show_subs_pane.nothing_selected();
        }
    });

    $("#subscriptions_table").on("click", ".email-address", function () {
        selectText(this);
    });

    $("#subscriptions_table").on("click", ".stream-row, .create_stream_button", show_right_section);

    $("#subscriptions_table").on("click", ".fa-chevron-left", () => {
        $(".right").removeClass("show");
        $(".subscriptions-header").removeClass("slide-left");
    });

    {
        const sel = ".search-container, .streams-list, .subscriptions-header";

        $("#subscriptions_table").on("click", sel, (e) => {
            if ($(e.target).is(sel)) {
                stream_edit.open_edit_panel_empty();
            }
        });
    }
}
