import $ from "jquery";
import _ from "lodash";

import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";
import render_stream_creation_confirmation_banner from "../templates/modal_banner/stream_creation_confirmation_banner.hbs";
import render_browse_streams_list from "../templates/stream_settings/browse_streams_list.hbs";
import render_browse_streams_list_item from "../templates/stream_settings/browse_streams_list_item.hbs";
import render_first_stream_created_modal from "../templates/stream_settings/first_stream_created_modal.hbs";
import render_stream_settings from "../templates/stream_settings/stream_settings.hbs";
import render_stream_settings_overlay from "../templates/stream_settings/stream_settings_overlay.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as components from "./components";
import * as compose_banner from "./compose_banner";
import * as compose_recipient from "./compose_recipient";
import * as compose_state from "./compose_state";
import * as dialog_widget from "./dialog_widget";
import * as hash_parser from "./hash_parser";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as message_lists from "./message_lists";
import * as message_live_update from "./message_live_update";
import * as message_view_header from "./message_view_header";
import * as overlays from "./overlays";
import * as resize from "./resize";
import * as scroll_util from "./scroll_util";
import * as search_util from "./search_util";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import {current_user, realm} from "./state_data";
import * as stream_create from "./stream_create";
import * as stream_data from "./stream_data";
import * as stream_edit from "./stream_edit";
import * as stream_edit_subscribers from "./stream_edit_subscribers";
import * as stream_edit_toggler from "./stream_edit_toggler";
import * as stream_list from "./stream_list";
import * as stream_settings_api from "./stream_settings_api";
import * as stream_settings_components from "./stream_settings_components";
import * as stream_settings_data from "./stream_settings_data";
import * as stream_ui_updates from "./stream_ui_updates";
import * as sub_store from "./sub_store";
import * as util from "./util";

export function is_sub_already_present(sub) {
    return stream_ui_updates.row_for_stream_id(sub.stream_id).length > 0;
}

export function update_left_panel_row(sub) {
    const $row = stream_ui_updates.row_for_stream_id(sub.stream_id);

    if ($row.length === 0) {
        return;
    }

    blueslip.debug(`Updating row in left panel of stream settings for: ${sub.name}`);
    const setting_sub = stream_settings_data.get_sub_for_settings(sub);
    const html = render_browse_streams_list_item(setting_sub);
    const $new_row = $(html);

    // TODO: Clean up this hack when we eliminate `notdisplayed`
    if ($row.hasClass("notdisplayed")) {
        $new_row.addClass("notdisplayed");
    }

    // TODO: Remove this if/when we just handle "active" when rendering templates.
    if ($row.hasClass("active")) {
        $new_row.addClass("active");
    }

    $row.replaceWith($new_row);
}

function get_row_data($row) {
    const row_id = Number.parseInt($row.attr("data-stream-id"), 10);
    if (row_id) {
        const row_object = sub_store.get(row_id);
        return {
            id: row_id,
            object: row_object,
        };
    }
    return undefined;
}

function selectText(element) {
    const sel = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(element);

    sel.removeAllRanges();
    sel.addRange(range);
}

function should_list_all_streams() {
    return !realm.realm_is_zephyr_mirror_realm;
}

export function toggle_pin_to_top_stream(sub) {
    stream_settings_api.set_stream_property(sub, {property: "pin_to_top", value: !sub.pin_to_top});
}

export function update_stream_name(sub, new_name) {
    // Rename the stream internally.
    stream_data.rename_sub(sub, new_name);
    const stream_id = sub.stream_id;

    // Update the left sidebar.
    stream_list.rename_stream(sub, new_name);

    // Update the stream settings
    stream_edit.update_stream_name(sub, new_name);

    // Update the subscriptions page
    const $sub_row = stream_ui_updates.row_for_stream_id(stream_id);
    $sub_row.find(".stream-name").text(new_name);

    // Update the message feed.
    message_live_update.update_stream_name(stream_id, new_name);

    // Update compose UI if needed
    if (compose_state.stream_id() === stream_id) {
        compose_recipient.on_compose_select_recipient_update();
    }

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function update_stream_description(sub, description, rendered_description) {
    sub.description = description;
    sub.rendered_description = rendered_description;
    stream_data.clean_up_description(sub);

    // Update stream row
    const $sub_row = stream_ui_updates.row_for_stream_id(sub.stream_id);
    $sub_row.find(".description").html(util.clean_user_content_links(sub.rendered_description));

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
    message_lists.current?.update_trailing_bookend();
    stream_ui_updates.update_setting_element(sub, "stream_privacy");
    stream_ui_updates.enable_or_disable_permission_settings_in_edit_panel(sub);
    stream_ui_updates.update_stream_privacy_icon_in_settings(sub);
    stream_ui_updates.update_settings_button_for_sub(sub);
    stream_ui_updates.update_add_subscriptions_elements(sub);
    stream_ui_updates.enable_or_disable_subscribers_tab(sub);
    stream_ui_updates.update_regular_sub_settings(sub);
    stream_list.redraw_stream_privacy(sub);

    const active_data = stream_settings_components.get_active_data();
    if (active_data.id === sub.stream_id) {
        stream_settings_components.set_right_panel_title(sub);
    }

    // Update navbar if needed
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function update_stream_post_policy(sub, new_value) {
    stream_data.update_stream_post_policy(sub, new_value);
    stream_ui_updates.update_setting_element(sub, "stream_post_policy");
}

export function update_message_retention_setting(sub, new_value) {
    stream_data.update_message_retention_setting(sub, new_value);
    stream_ui_updates.update_setting_element(sub, "message_retention_days");
}

export function update_can_remove_subscribers_group_id(sub, new_value) {
    stream_data.update_can_remove_subscribers_group_id(sub, new_value);
    stream_ui_updates.update_setting_element(sub, "can_remove_subscribers_group");
    stream_edit_subscribers.rerender_subscribers_list(sub);
}

export function update_is_default_stream() {
    const active_stream_id = stream_settings_components.get_active_data().id;
    if (active_stream_id) {
        const sub = sub_store.get(active_stream_id);
        stream_ui_updates.update_setting_element(sub, "is_default_stream");
    }
}

export function update_subscribers_ui(sub) {
    update_left_panel_row(sub);
    stream_edit_subscribers.update_subscribers_list(sub);
    message_view_header.maybe_rerender_title_area_for_stream(sub);
}

export function add_sub_to_table(sub) {
    if (is_sub_already_present(sub)) {
        // If a stream is already listed/added in subscription modal,
        // display stream in `Subscribed` tab and return.
        // This can happen in some corner cases (which might
        // be backend bugs) where a realm administrator is subscribed
        // to a private stream, in which case they might get two
        // stream-create events.
        stream_ui_updates.update_stream_row_in_settings_tab(sub);
        return;
    }

    const setting_sub = stream_settings_data.get_sub_for_settings(sub);
    const html = render_browse_streams_list_item(setting_sub);
    const $new_row = $(html);

    if (stream_create.get_name() === sub.name) {
        scroll_util.get_content_element($(".streams-list")).prepend($new_row);
        scroll_util.reset_scrollbar($(".streams-list"));
    } else {
        scroll_util.get_content_element($(".streams-list")).append($new_row);
    }

    const settings_html = render_stream_settings({
        sub: stream_settings_data.get_sub_for_settings(sub),
    });
    scroll_util
        .get_content_element($("#channels_overlay_container .settings"))
        .append($(settings_html));

    if (stream_create.get_name() === sub.name) {
        // This `stream_create.get_name()` check tells us whether the
        // stream was just created in this browser window; it's a hack
        // to work around the server_events code flow not having a
        // good way to associate with this request because the stream
        // ID isn't known yet.  These are appended to the top of the
        // list, so they are more visible.
        stream_ui_updates.row_for_stream_id(sub.stream_id).trigger("click");
        const context = {
            banner_type: compose_banner.SUCCESS,
            classname: "stream_creation_confirmation",
            stream_name: sub.name,
            stream_url: hash_util.by_stream_url(sub.stream_id),
        };
        $("#stream_settings .stream-creation-confirmation-banner").html(
            render_stream_creation_confirmation_banner(context),
        );
        stream_create.reset_created_stream();
        // goto topic `stream events` of the newly created stream
        browser_history.go_to_location(hash_util.by_stream_url(sub.stream_id));
        if (stream_create.should_show_first_stream_created_modal()) {
            stream_create.set_first_stream_created_modal_shown();
            show_first_stream_created_modal(sub);
        }
    }
    update_empty_left_panel_message();
}
function show_first_stream_created_modal(stream) {
    dialog_widget.launch({
        html_heading: $t_html(
            {defaultMessage: "Channel <b><z-stream></z-stream></b> created!"},
            {
                "z-stream": () => render_inline_decorated_stream_name({stream}),
            },
        ),
        html_body: render_first_stream_created_modal({stream}),
        id: "first_stream_created_modal",
        on_click() {},
        html_submit_button: $t({defaultMessage: "Continue"}),
        close_on_submit: true,
        single_footer_button: true,
    });
}

export function remove_stream(stream_id) {
    // It is possible that row is empty when we deactivate a
    // stream, but we let jQuery silently handle that.
    const $row = stream_ui_updates.row_for_stream_id(stream_id);
    $row.remove();
    update_empty_left_panel_message();
    if (hash_parser.is_editing_stream(stream_id)) {
        stream_edit.open_edit_panel_empty();
    }
}

export function update_settings_for_subscribed(slim_sub) {
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    stream_ui_updates.update_add_subscriptions_elements(sub);
    $(
        `.stream_settings_header[data-stream-id='${CSS.escape(
            sub.stream_id,
        )}'] #preview-stream-button`,
    ).show();

    if (is_sub_already_present(sub)) {
        update_left_panel_row(sub);
        stream_ui_updates.update_toggler_for_sub(sub);
        stream_ui_updates.update_stream_row_in_settings_tab(sub);
        stream_ui_updates.update_settings_button_for_sub(sub);
        stream_ui_updates.enable_or_disable_permission_settings_in_edit_panel(sub);
    } else {
        add_sub_to_table(sub);
    }

    stream_edit_subscribers.update_subscribers_list(sub);

    // Display the swatch and subscription stream_settings
    stream_ui_updates.update_regular_sub_settings(sub);
    stream_ui_updates.update_permissions_banner(sub);

    // Update whether there's any streams shown or not.
    update_empty_left_panel_message();
}

export function show_active_stream_in_left_panel() {
    const selected_row = hash_parser.get_current_hash_section();

    if (Number.parseFloat(selected_row)) {
        const $sub_row = stream_ui_updates.row_for_stream_id(selected_row);
        $sub_row.addClass("active");
    }
}

export function update_settings_for_unsubscribed(slim_sub) {
    const sub = stream_settings_data.get_sub_for_settings(slim_sub);
    update_left_panel_row(sub);
    stream_edit_subscribers.update_subscribers_list(sub);
    stream_ui_updates.update_toggler_for_sub(sub);
    stream_ui_updates.update_settings_button_for_sub(sub);
    stream_ui_updates.update_regular_sub_settings(sub);
    stream_ui_updates.enable_or_disable_permission_settings_in_edit_panel(sub);

    // If user unsubscribed from private stream then user cannot subscribe to
    // stream without invitation and cannot add subscribers to stream.
    if (!stream_data.can_toggle_subscription(sub)) {
        stream_ui_updates.update_add_subscriptions_elements(sub);
    }
    if (current_user.is_guest) {
        stream_edit.open_edit_panel_empty();
    }

    // Remove private streams from subscribed streams list.
    stream_ui_updates.update_stream_row_in_settings_tab(sub);
    stream_ui_updates.update_permissions_banner(sub);

    update_empty_left_panel_message();
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
    const html = render_browse_streams_list({
        subscriptions: stream_settings_data.get_updated_unsorted_subs(),
    });

    scroll_util.get_content_element($("#channels_overlay_container .streams-list")).html(html);
}

export function update_empty_left_panel_message() {
    // Check if we have any streams in panel to decide whether to
    // display a notice.
    let has_streams;
    if (stream_ui_updates.is_subscribed_stream_tab_active()) {
        // We don't remove stream row from UI on unsubscribe, To handle
        // this case here we are also checking DOM if there are streams
        // displayed in panel or not.
        has_streams =
            stream_data.subscribed_subs().length ||
            $("#channels_overlay_container .stream-row:not(.notdisplayed)").length;
    } else {
        has_streams = stream_data.get_unsorted_subs().length;
    }
    if (has_streams) {
        $(".no-streams-to-show").hide();
        return;
    }
    if (stream_ui_updates.is_subscribed_stream_tab_active()) {
        $(".all_streams_tab_empty_text").hide();
        $(".subscribed_streams_tab_empty_text").show();
    } else {
        $(".subscribed_streams_tab_empty_text").hide();
        $(".all_streams_tab_empty_text").show();
    }
    $(".no-streams-to-show").show();
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

    for (const row of $("#channels_overlay_container .stream-row")) {
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

    for (const row of $("#channels_overlay_container .stream-row")) {
        const stream_id = stream_id_for_row(row);

        // Below code goes away if we don't do sort-DOM-in-place.
        if (hidden_ids.has(stream_id)) {
            $(row).addClass("notdisplayed");
        } else {
            $(row).removeClass("notdisplayed");
        }

        widgets.set(stream_id, $(row).detach());
    }

    scroll_util.reset_scrollbar($("#subscription_overlay .streams-list"));

    const all_stream_ids = [...buckets.name, ...buckets.desc, ...buckets.other];

    for (const stream_id of all_stream_ids) {
        scroll_util
            .get_content_element($("#channels_overlay_container .streams-list"))
            .append(widgets.get(stream_id));
    }
    update_empty_left_panel_message();

    // return this for test convenience
    return [...buckets.name, ...buckets.desc];
}

let sort_order = "by-stream-name";

export function get_left_panel_params() {
    const $search_box = $("#stream_filter input[type='text']");
    const input = $search_box.expectOne().val().trim();
    const params = {
        input,
        subscribed_only: stream_ui_updates.subscribed_only,
        sort_order,
    };
    return params;
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
        stream_ui_updates.set_subscribed_only(false);
    } else if (tab_name === "subscribed") {
        stream_ui_updates.set_subscribed_only(true);
    }

    redraw_left_panel();
    if ($(".stream-row.active").hasClass("notdisplayed")) {
        stream_edit.empty_right_panel();
    }
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
    // time we go into "Stream settings" is that we used to have
    // some live-update issues, so being able to re-launch the
    // streams page is kind of a workaround for those bugs, since
    // we will re-populate the widget.
    //
    // For now, every time we go back into the widget we'll
    // continue the strategy that we re-render everything from scratch.
    // Also, we'll always go back to the "Subscribed" tab.
    function initialize_components() {
        // Sort by name by default when opening "Stream settings".
        sort_order = "by-stream-name";
        const sort_toggler = components.toggle({
            values: [
                {
                    label_html: `<i class="fa fa-sort-alpha-asc" data-tippy-content="${$t({
                        defaultMessage: "Sort by name",
                    })}"></i>`,
                    key: "by-stream-name",
                },
                {
                    label_html: `<i class="fa fa-user-o" data-tippy-content="${$t({
                        defaultMessage: "Sort by number of subscribers",
                    })}"></i>`,
                    key: "by-subscriber-count",
                },
                {
                    label_html: `<i class="fa fa-bar-chart" data-tippy-content="${$t({
                        defaultMessage: "Sort by estimated weekly traffic",
                    })}"></i>`,
                    key: "by-weekly-traffic",
                },
            ],
            html_class: "stream_sorter_toggle",
            callback(_value, key) {
                switch_stream_sort(key);
            },
        });

        sort_toggler.get().prependTo("#channels_overlay_container .list-toggler-container");

        // Reset our internal state to reflect that we're initially in
        // the "Subscribed" tab if we're reopening "Stream settings".
        stream_ui_updates.set_subscribed_only(true);
        toggler = components.toggle({
            child_wants_focus: true,
            values: [
                {label: $t({defaultMessage: "Subscribed"}), key: "subscribed"},
                {label: $t({defaultMessage: "All channels"}), key: "all-streams"},
            ],
            callback(_value, key) {
                switch_stream_tab(key);
            },
        });

        if (should_list_all_streams()) {
            const $toggler_elem = toggler.get();
            $("#channels_overlay_container .list-toggler-container").prepend($toggler_elem);
        }
        if (current_user.is_guest) {
            toggler.disable_tab("all-streams");
        }

        // show the "Stream settings" header by default.
        $(".display-type #stream_settings_title").show();
    }

    function populate_and_fill() {
        $("#channels_overlay_container").empty();

        // TODO: Ideally we'd indicate in some way what stream types
        // the user can create, by showing other options as disabled.
        const stream_privacy_policy = settings_config.stream_privacy_policy_values.public.code;
        const new_stream_announcements_stream = stream_data.get_new_stream_announcements_stream();
        const new_stream_announcements_stream_sub = stream_data.get_sub_by_name(
            new_stream_announcements_stream,
        );

        const template_data = {
            new_stream_announcements_stream_sub,
            ask_to_announce_stream: true,
            can_create_streams:
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams(),
            can_view_all_streams: !current_user.is_guest && should_list_all_streams(),
            max_stream_name_length: realm.max_stream_name_length,
            max_stream_description_length: realm.max_stream_description_length,
            is_owner: current_user.is_owner,
            stream_privacy_policy_values: settings_config.stream_privacy_policy_values,
            stream_privacy_policy,
            stream_post_policy_values: settings_config.stream_post_policy_values,
            check_default_stream: false,
            zulip_plan_is_not_limited: realm.zulip_plan_is_not_limited,
            org_level_message_retention_setting:
                stream_edit.get_display_text_for_realm_message_retention_setting(),
            upgrade_text_for_wide_organization_logo: realm.upgrade_text_for_wide_organization_logo,
            is_business_type_org:
                realm.realm_org_type === settings_config.all_org_type_values.business.code,
            disable_message_retention_setting:
                !realm.zulip_plan_is_not_limited || !current_user.is_owner,
        };

        const rendered = render_stream_settings_overlay(template_data);
        $("#channels_overlay_container").append($(rendered));

        render_left_panel_superset();
        initialize_components();
        stream_settings_components.dropdown_setup();
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
        // implicitly because realm.realm_is_zephyr_mirror_realm.
        $("#stream_filter input[type='text']").on("keypress", (e) => {
            if (!keydown_util.is_enter_event(e)) {
                return;
            }

            if (
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams() ||
                realm.realm_is_zephyr_mirror_realm
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
    const $stream_row = stream_ui_updates.row_for_stream_id(stream_id);
    const $container = $(".streams-list");

    stream_settings_components.get_active_data().$row.removeClass("active");
    $stream_row.addClass("active");

    scroll_util.scroll_element_into_container($stream_row, $container);

    stream_edit.open_edit_panel_for_row($stream_row);
}

function show_right_section() {
    $(".right").addClass("show");
    $(".subscriptions-header").addClass("slide-left");
    resize.resize_stream_subscribers_list();
}

export function change_state(section, left_side_tab, right_side_tab) {
    // if in #channels/new form.
    if (section === "new") {
        do_open_create_stream();
        show_right_section();
        return;
    }

    if (section === "all") {
        toggler.goto("all-streams");
        stream_edit.empty_right_panel();
        return;
    }

    // if the section is a valid number.
    if (/\d+/.test(section)) {
        const stream_id = Number.parseInt(section, 10);
        show_right_section();
        stream_edit_toggler.set_select_tab(right_side_tab);

        if (left_side_tab === undefined) {
            left_side_tab = "all-streams";
            if (stream_data.is_subscribed(stream_id)) {
                left_side_tab = "subscribed";
            }
        }

        // Callback to .goto() will update browser_history unless a
        // stream is being edited. We are always editing a stream here
        // so its safe to call
        if (left_side_tab !== toggler.value()) {
            toggler.goto(left_side_tab);
        }
        switch_to_stream_row(stream_id);
        return;
    }

    toggler.goto("subscribed");
    stream_edit.empty_right_panel();
}

export function launch(section, left_side_tab, right_side_tab) {
    setup_page(() => {
        overlays.open_overlay({
            name: "subscriptions",
            $overlay: $("#subscription_overlay"),
            on_close() {
                browser_history.exit_overlay();
                $(".colorpicker").spectrum("destroy");
            },
        });
        change_state(section, left_side_tab, right_side_tab);
    });
    if (!stream_settings_components.get_active_data().id) {
        if (section === "new") {
            $("#create_stream_name").trigger("focus");
        } else {
            $("#search_stream_name").trigger("focus");
        }
    }
}

export function switch_rows(event) {
    const active_data = stream_settings_components.get_active_data();
    const $add_subscriber_pill_input = $(".add_subscribers_container .input");
    let $switch_row;
    if (hash_parser.is_create_new_stream_narrow()) {
        // Prevent switching stream rows when creating a new stream
        return false;
    } else if (
        hash_parser.is_subscribers_section_opened_for_stream() &&
        $add_subscriber_pill_input.is(":focus")
    ) {
        // Prevent switching stream rows when adding a subscriber
        return false;
    } else if (!active_data.id || active_data.$row.hasClass("notdisplayed")) {
        $switch_row = $("div.stream-row:not(.notdisplayed)").first();
        if ($("#search_stream_name").is(":focus")) {
            $("#search_stream_name").trigger("blur");
        }
    } else {
        if (event === "up_arrow") {
            $switch_row = active_data.$row.prevAll().not(".notdisplayed").first();
        } else if (event === "down_arrow") {
            $switch_row = active_data.$row.nextAll().not(".notdisplayed").first();
        }
        if ($("#search_stream_name").is(":focus")) {
            // remove focus from Filter streams input instead of switching rows
            // if Filter streams input is focused
            return $("#search_stream_name").trigger("blur");
        }
    }

    const row_data = get_row_data($switch_row);
    if (row_data) {
        const stream_id = row_data.id;
        switch_to_stream_row(stream_id);
    } else if (event === "up_arrow" && !row_data) {
        $("#search_stream_name").trigger("focus");
    }
    return true;
}

export function keyboard_sub() {
    const active_data = stream_settings_components.get_active_data();
    const row_data = get_row_data(active_data.$row);
    if (row_data) {
        stream_settings_components.sub_or_unsub(row_data.object);
    }
}

export function toggle_view(event) {
    const active_data = stream_settings_components.get_active_data();
    const stream_filter_tab = active_data.$tabs.first().text();

    if (event === "right_arrow" && stream_filter_tab === "Subscribed") {
        toggler.goto("all-streams");
    } else if (event === "left_arrow" && stream_filter_tab === "All channels") {
        toggler.goto("subscribed");
    }
}

export function view_stream() {
    const active_data = stream_settings_components.get_active_data();
    const row_data = get_row_data(active_data.$row);
    if (row_data) {
        const stream_narrow_hash =
            "#narrow/stream/" + hash_util.encode_stream_name(row_data.object.name);
        browser_history.go_to_location(stream_narrow_hash);
    }
}

export function do_open_create_stream() {
    // Only call this directly for hash changes.
    // Prefer open_create_stream().

    const stream = $("#search_stream_name").val().trim();

    if (!should_list_all_streams()) {
        // Realms that don't allow listing streams should simply be subscribed to.
        stream_create.set_name(stream);
        stream_settings_components.ajaxSubscribe($("#search_stream_name").val());
        return;
    }

    stream_create.new_stream_clicked(stream);
}

export function open_create_stream() {
    do_open_create_stream();
    browser_history.update("#channels/new");
}

export function update_stream_privacy_choices(policy) {
    if (!overlays.streams_open()) {
        return;
    }
    const stream_edit_panel_opened = $("#stream_permission_settings").is(":visible");
    const stream_creation_form_opened = $("#stream-creation").is(":visible");

    if (!stream_edit_panel_opened && !stream_creation_form_opened) {
        return;
    }
    let $container = $("#stream-creation");
    if (stream_edit_panel_opened) {
        $container = $("#stream_permission_settings");
    }

    if (policy === "create_private_stream_policy") {
        stream_ui_updates.update_private_stream_privacy_option_state($container);
    }
    if (policy === "create_public_stream_policy") {
        stream_settings_components.update_public_stream_privacy_option_state($container);
    }
    if (policy === "create_web_public_stream_policy") {
        stream_ui_updates.update_web_public_stream_privacy_option_state($container);
    }
}

export function initialize() {
    $("#channels_overlay_container").on("click", ".create_stream_button", (e) => {
        e.preventDefault();
        open_create_stream();
    });

    $("#channels_overlay_container").on("click", "#stream_creation_form [data-dismiss]", (e) => {
        e.preventDefault();
        // we want to make sure that the click is not just a simulated
        // click; this fixes an issue where hitting "Enter" would
        // trigger this code path due to bootstrap magic.
        if (e.clientY !== 0) {
            stream_edit.open_edit_panel_empty();
        }
    });

    $("#channels_overlay_container").on("click", ".email-address", function () {
        selectText(this);
    });

    $("#channels_overlay_container").on(
        "click",
        ".stream-row, .create_stream_button",
        show_right_section,
    );

    $("#channels_overlay_container").on("click", ".fa-chevron-left", () => {
        $(".right").removeClass("show");
        $(".subscriptions-header").removeClass("slide-left");
    });
}
