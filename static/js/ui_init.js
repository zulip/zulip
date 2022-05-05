import $ from "jquery";
import _ from "lodash";

import generated_emoji_codes from "../generated/emoji/emoji_codes.json";
import generated_pygments_data from "../generated/pygments_data.json";
import * as fenced_code from "../shared/js/fenced_code";
import render_compose from "../templates/compose.hbs";
import render_edit_content_button from "../templates/edit_content_button.hbs";
import render_left_sidebar from "../templates/left_sidebar.hbs";
import render_message_feed_errors from "../templates/message_feed_errors.hbs";
import render_navbar from "../templates/navbar.hbs";
import render_right_sidebar from "../templates/right_sidebar.hbs";

import * as about_zulip from "./about_zulip";
import * as activity from "./activity";
import * as alert_words from "./alert_words";
import * as blueslip from "./blueslip";
import * as bot_data from "./bot_data";
import * as click_handlers from "./click_handlers";
import * as common from "./common";
import * as compose from "./compose";
import * as compose_closed_ui from "./compose_closed_ui";
import * as compose_pm_pill from "./compose_pm_pill";
import * as composebox_typeahead from "./composebox_typeahead";
import * as condense from "./condense";
import * as copy_and_paste from "./copy_and_paste";
import * as dark_theme from "./dark_theme";
import * as drafts from "./drafts";
import * as echo from "./echo";
import * as emoji from "./emoji";
import * as emoji_picker from "./emoji_picker";
import * as emojisets from "./emojisets";
import * as gear_menu from "./gear_menu";
import * as giphy from "./giphy";
import * as hashchange from "./hashchange";
import * as hotspots from "./hotspots";
import * as i18n from "./i18n";
import * as invite from "./invite";
import * as lightbox from "./lightbox";
import * as linkifiers from "./linkifiers";
import {localstorage} from "./localstorage";
import * as markdown from "./markdown";
import * as markdown_config from "./markdown_config";
import * as message_edit from "./message_edit";
import * as message_edit_history from "./message_edit_history";
import * as message_fetch from "./message_fetch";
import * as message_lists from "./message_lists";
import * as message_scroll from "./message_scroll";
import * as message_view_header from "./message_view_header";
import * as message_viewport from "./message_viewport";
import * as muted_topics from "./muted_topics";
import * as muted_users from "./muted_users";
import * as navbar_alerts from "./navbar_alerts";
import * as navigate from "./navigate";
import * as notifications from "./notifications";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as pm_conversations from "./pm_conversations";
import * as popover_menus from "./popover_menus";
import * as presence from "./presence";
import * as realm_logo from "./realm_logo";
import * as realm_playground from "./realm_playground";
import * as realm_user_settings_defaults from "./realm_user_settings_defaults";
import * as recent_topics_util from "./recent_topics_util";
import * as reload from "./reload";
import * as rendered_markdown from "./rendered_markdown";
import * as resize from "./resize";
import * as rows from "./rows";
import * as scroll_bar from "./scroll_bar";
import * as search from "./search";
import * as search_pill_widget from "./search_pill_widget";
import * as sent_messages from "./sent_messages";
import * as server_events from "./server_events";
import * as settings from "./settings";
import * as settings_data from "./settings_data";
import * as settings_display from "./settings_display";
import * as settings_notifications from "./settings_notifications";
import * as settings_panel_menu from "./settings_panel_menu";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults";
import * as settings_sections from "./settings_sections";
import * as settings_toggle from "./settings_toggle";
import * as spoilers from "./spoilers";
import * as starred_messages from "./starred_messages";
import * as stream_bar from "./stream_bar";
import * as stream_data from "./stream_data";
import * as stream_edit from "./stream_edit";
import * as stream_edit_subscribers from "./stream_edit_subscribers";
import * as stream_list from "./stream_list";
import * as stream_settings_ui from "./stream_settings_ui";
import * as timerender from "./timerender";
import * as tippyjs from "./tippyjs";
import * as topic_list from "./topic_list";
import * as topic_zoom from "./topic_zoom";
import * as tutorial from "./tutorial";
import * as typing from "./typing";
import * as ui from "./ui";
import * as unread from "./unread";
import * as unread_ui from "./unread_ui";
import * as user_groups from "./user_groups";
import {initialize_user_settings, user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_status_ui from "./user_status_ui";

// This is where most of our initialization takes place.
// TODO: Organize it a lot better.  In particular, move bigger
//       functions to other modules.

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

let $current_message_hover;
function message_unhover() {
    if ($current_message_hover === undefined) {
        return;
    }
    $current_message_hover.find("span.edit_content").html("");
    $current_message_hover = undefined;
}

function message_hover($message_row) {
    const id = rows.id($message_row);
    if ($current_message_hover && rows.id($current_message_hover) === id) {
        return;
    }

    const message = message_lists.current.get(rows.id($message_row));
    message_unhover();
    $current_message_hover = $message_row;

    // Locally echoed messages have !is_topic_editable and thus go
    // through this code path.
    if (!message_edit.is_topic_editable(message)) {
        // The actions and reactions icon hover logic is handled entirely by CSS
        return;
    }

    // But the message edit hover icon is determined by whether the message is still editable
    const is_message_editable =
        message_edit.get_editability(message) === message_edit.editability_types.FULL;
    const args = {
        is_editable: is_message_editable && !message.status_message,
        msg_id: id,
    };
    $message_row.find(".edit_content").html(render_edit_content_button(args));
}

function initialize_left_sidebar() {
    const rendered_sidebar = render_left_sidebar({
        is_guest: page_params.is_guest,
    });

    $("#left-sidebar-container").html(rendered_sidebar);
}

function initialize_right_sidebar() {
    const rendered_sidebar = render_right_sidebar({
        can_invite_others_to_realm: settings_data.user_can_invite_others_to_realm(),
        realm_rendered_description: page_params.realm_rendered_description,
    });

    $("#right-sidebar-container").html(rendered_sidebar);
    if (page_params.is_spectator) {
        rendered_markdown.update_elements(
            $(".right-sidebar .realm-description .rendered_markdown"),
        );
    }

    $("#user_presences").on("mouseenter", ".user_sidebar_entry", (e) => {
        const $status_emoji = $(e.target).closest(".user_sidebar_entry").find("img.status_emoji");
        if ($status_emoji.length) {
            const animated_url = $status_emoji.data("animated-url");
            if (animated_url) {
                $status_emoji.attr("src", animated_url);
            }
        }
    });

    $("#user_presences").on("mouseleave", ".user_sidebar_entry", (e) => {
        const $status_emoji = $(e.target).closest(".user_sidebar_entry").find("img.status_emoji");
        if ($status_emoji.length) {
            const still_url = $status_emoji.data("still-url");
            if (still_url) {
                $status_emoji.attr("src", still_url);
            }
        }
    });
}

function initialize_navbar() {
    const rendered_navbar = render_navbar({
        embedded: page_params.narrow_stream !== undefined,
        search_pills_enabled: page_params.search_pills_enabled,
    });

    $("#navbar-container").html(rendered_navbar);
}

function initialize_compose_box() {
    $("#compose-container").append(
        render_compose({
            embedded: $("#compose").attr("data-embedded") === "",
            file_upload_enabled: page_params.max_file_upload_size_mib > 0,
            giphy_enabled: giphy.is_giphy_enabled(),
            scroll_to_bottom_key_html: common.has_mac_keyboard()
                ? "Fn + <span class='tooltip_right_arrow'>→</span>"
                : "End",
            narrow_to_compose_recipients_key_html:
                (common.has_mac_keyboard() ? "⌘" : "Ctrl") + " + .",
        }),
    );
    $(`.enter_sends_${user_settings.enter_sends}`).show();
    common.adjust_mac_shortcuts(".enter_sends kbd");
}

function initialize_message_feed_errors() {
    $("#message_feed_errors_container").html(render_message_feed_errors());
}

export function initialize_kitchen_sink_stuff() {
    // TODO:
    //      This function is a historical dumping ground
    //      for lots of miscellaneous setup.  Almost all of
    //      the code here can probably be moved to more
    //      specific-purpose modules like message_viewport.js.

    const throttled_mousewheelhandler = _.throttle((e, delta) => {
        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.

        if (delta < 0 && message_viewport.at_top()) {
            navigate.up();
        } else if (delta > 0 && message_viewport.at_bottom()) {
            navigate.down();
        }

        message_viewport.set_last_movement_direction(delta);
    }, 50);

    message_viewport.$message_pane.on("wheel", (e) => {
        const delta = e.originalEvent.deltaY;
        if (!overlays.is_overlay_or_modal_open() && !recent_topics_util.is_visible()) {
            // In the message view, we use a throttled mousewheel handler.
            throttled_mousewheelhandler(e, delta);
        }
        // If in a modal, we neither handle the event nor
        // preventDefault, allowing the modal to scroll normally.
    });

    $(window).on("resize", _.throttle(resize.handler, 50));

    // Scrolling in overlays. input boxes, and other elements that
    // explicitly scroll should not scroll the main view.  Stop
    // propagation in all cases.  Also, ignore the event if the
    // element is already at the top or bottom.  Otherwise we get a
    // new scroll event on the parent (?).
    $(".modal-body, .scrolling_list, input, textarea").on("wheel", function (e) {
        const $self = ui.get_scroll_element($(this));
        const scroll = $self.scrollTop();
        const delta = e.originalEvent.deltaY;

        // The -1 fudge factor is important here due to rounding errors.  Better
        // to err on the side of not scrolling.
        const max_scroll = $self.prop("scrollHeight") - $self.innerHeight() - 1;

        e.stopPropagation();
        if ((delta < 0 && scroll <= 0) || (delta > 0 && scroll >= max_scroll)) {
            e.preventDefault();
        }
    });

    // Ignore wheel events in the compose area which weren't already handled above.
    $("#compose").on("wheel", (e) => {
        e.stopPropagation();
        e.preventDefault();
    });

    // A little hackish, because it doesn't seem to totally get us the
    // exact right width for the floating_recipient_bar and compose
    // box, but, close enough for now.
    resize.handler();

    if (page_params.is_spectator) {
        $("body").addClass("spectator-view");
    }

    if (!user_settings.left_side_userlist) {
        $("#navbar-buttons").addClass("right-userlist");
    }

    if (user_settings.high_contrast_mode) {
        $("body").addClass("high-contrast");
    }

    if (!user_settings.dense_mode) {
        $("body").addClass("less_dense_mode");
    } else {
        $("body").addClass("more_dense_mode");
    }

    $("#main_div").on("mouseover", ".message_table .message_row", function () {
        const $row = $(this).closest(".message_row");
        message_hover($row);
    });

    $("#main_div").on("mouseleave", ".message_table .message_row", () => {
        message_unhover();
    });

    $("#main_div").on("mouseover", ".sender_info_hover", function () {
        const $row = $(this).closest(".message_row");
        $row.addClass("sender_name_hovered");
    });

    $("#main_div").on("mouseout", ".sender_info_hover", function () {
        const $row = $(this).closest(".message_row");
        $row.removeClass("sender_name_hovered");
    });

    function handle_video_preview_mouseenter($elem) {
        // Set image height and css vars for play button position, if not done already
        const setPosition = !$elem.data("entered-before");
        if (setPosition) {
            const imgW = $elem.find("img")[0].width;
            const imgH = $elem.find("img")[0].height;
            // Ensure height doesn't change on mouse enter
            $elem.css("height", `${imgH}px`);
            // variables to set play button position
            const marginLeft = (imgW - 30) / 2;
            const marginTop = (imgH - 26) / 2;
            $elem.css("--margin-left", `${marginLeft}px`).css("--margin-top", `${marginTop}px`);
            $elem.data("entered-before", true);
        }
        $elem.addClass("fa fa-play");
    }

    $("#main_div").on("mouseenter", ".youtube-video a", function () {
        handle_video_preview_mouseenter($(this));
    });

    $("#main_div").on("mouseleave", ".youtube-video a", function () {
        $(this).removeClass("fa fa-play");
    });

    $("#main_div").on("mouseenter", ".embed-video a", function () {
        handle_video_preview_mouseenter($(this));
    });

    $("#main_div").on("mouseleave", ".embed-video a", function () {
        $(this).removeClass("fa fa-play");
    });

    $("#manage_streams_container").on("mouseover", ".subscription_header", function () {
        $(this).addClass("active");
    });

    $("#manage_streams_container").on("mouseout", ".subscription_header", function () {
        $(this).removeClass("active");
    });

    $("#stream_message_recipient_stream").on("change", function () {
        stream_bar.decorate(this.value, $("#stream-message .message_header_stream"), true);
    });

    $(window).on("blur", () => {
        $(document.body).addClass("window_blurred");
    });

    $(window).on("focus", () => {
        $(document.body).removeClass("window_blurred");
    });

    $(document).on("message_selected.zulip", (event) => {
        if (message_lists.current !== event.msg_list) {
            return;
        }
        if (event.id === -1) {
            // If the message list is empty, don't do anything
            return;
        }
        const $row = event.msg_list.get_row(event.id);
        $(".selected_message").removeClass("selected_message");
        $row.addClass("selected_message");

        if (event.then_scroll) {
            if ($row.length === 0) {
                const $row_from_dom = message_lists.current.get_row(event.id);
                const messages = event.msg_list.all_messages();
                blueslip.debug("message_selected missing selected row", {
                    previously_selected_id: event.previously_selected_id,
                    selected_id: event.id,
                    selected_idx: event.msg_list.selected_idx(),
                    selected_idx_exact: messages.indexOf(event.msg_list.get(event.id)),
                    render_start: event.msg_list.view._render_win_start,
                    render_end: event.msg_list.view._render_win_end,
                    selected_id_from_idx: messages[event.msg_list.selected_idx()].id,
                    msg_list_sorted: _.isEqual(
                        messages.map((message) => message.id),
                        message_lists.current
                            .all_messages()
                            .map((message) => message.id)
                            .sort(),
                    ),
                    found_in_dom: $row_from_dom.length,
                });
            }
            if (event.target_scroll_offset !== undefined) {
                message_lists.current.view.set_message_offset(event.target_scroll_offset);
            } else {
                // Scroll to place the message within the current view;
                // but if this is the initial placement of the pointer,
                // just place it in the very center
                message_viewport.recenter_view($row, {
                    from_scroll: event.from_scroll,
                    force_center: event.previously_selected_id === -1,
                });
            }
        }
    });

    $("body").on("mouseover", ".message_edit_content", function () {
        $(this).closest(".message_row").find(".copy_message").show();
    });

    $("body").on("mouseout", ".message_edit_content", function () {
        $(this).closest(".message_row").find(".copy_message").hide();
    });

    $("body").on("mouseenter", ".copy_message", function () {
        $(this).show();
    });

    if (!page_params.realm_allow_message_editing) {
        $("#edit-message-hotkey-help").hide();
    }

    if (page_params.realm_presence_disabled) {
        $("#user-list").hide();
    }
}

export function initialize_everything() {
    /*
        When we initialize our various modules, a lot
        of them will consume data from the server
        in the form of `page_params`.

        The `page_params` variable is basically a
        massive dictionary with all the information
        that the client needs to run the app.  Here
        are some examples of what it includes:

            - all of the user's user-specific settings
            - all realm-specific settings that are
              pertinent to the user
            - info about streams/subscribers on the realm
            - realm settings
            - info about all the other users
            - some fairly dynamic data, like which of
              the other users are "present"

        Except for the actual Zulip messages, basically
        any data that you see in the app soon after page
        load comes from `page_params`.

        ## Mostly static data

        Now, we mostly leave `page_params` intact through
        the duration of the app.  Most of the data in
        `page_params` is fairly static in nature, and we
        will simply update it for basic changes like
        the following (meant as examples, not gospel):

            - I changed my 24-hour time preference.
            - The realm admin changed who can edit topics.
            - The team's realm icon has changed.
            - I switched from light theme to dark theme.

        Especially for things that are settings-related,
        we rarely abstract away the data from `page_params`.
        As of this writing, over 90 modules refer directly
        to `page_params` for some reason or another.

        ## Dynamic data

        Some of the data in `page_params` is either
        more highly dynamic than settings data, or
        has more performance requirements than
        simple settings data, or both.  Examples
        include:

            - tracking all users (we want to have
              multiple Maps to find users, for example)
            - tracking all streams
            - tracking presence data
            - tracking user groups and bots
            - tracking recent PMs

        Using stream data as an example, we use a
        module called `stream_data` to actually track
        all the info about the streams that a user
        can know about.  We populate this module
        with data from `page_params`, but thereafter
        `stream_data.js` "owns" the stream data:

            - other modules should ask `stream_data`
              for stuff (and not go to `page_params`)
            - when server events come in, they should
              be processed by stream_data to update
              its own data structures

        To help enforce this paradigm, we do the
        following:

            - only pass `stream_data` what it needs
              from `page_params`
            - delete the reference to data owned by
              `stream_data` in `page_params` itself
    */

    function pop_fields(...fields) {
        const result = {};

        for (const field of fields) {
            result[field] = page_params[field];
            delete page_params[field];
        }

        return result;
    }

    const alert_words_params = pop_fields("alert_words");

    const emoji_params = pop_fields("realm_emoji");

    const bot_params = pop_fields("realm_bots");

    const people_params = pop_fields("realm_users", "realm_non_active_users", "cross_realm_bots");

    const pm_conversations_params = pop_fields("recent_private_conversations");

    const presence_params = pop_fields("presences", "server_timestamp");

    const stream_data_params = pop_fields(
        "subscriptions",
        "unsubscribed",
        "never_subscribed",
        "realm_default_streams",
    );

    const user_groups_params = pop_fields("realm_user_groups");

    const user_status_params = pop_fields("user_status");
    const i18n_params = pop_fields("language_list");
    const user_settings_params = pop_fields("user_settings");
    const realm_settings_defaults_params = pop_fields("realm_user_settings_defaults");

    if (page_params.is_spectator) {
        const ls = localstorage();
        const preferred_theme = ls.get("spectator-theme-preference");
        if (preferred_theme === "dark") {
            dark_theme.enable();
        } else if (preferred_theme === "light") {
            dark_theme.disable();
        }
    }

    i18n.initialize(i18n_params);
    tippyjs.initialize();
    popover_menus.initialize();

    initialize_user_settings(user_settings_params);
    realm_user_settings_defaults.initialize(realm_settings_defaults_params);
    people.initialize(page_params.user_id, people_params);

    let date_joined;
    if (!page_params.is_spectator) {
        const user = people.get_by_user_id(page_params.user_id);
        date_joined = user.date_joined;
    } else {
        // Spectators don't have an account, so we just prevent their
        // date_joined is now.
        date_joined = new Date();
    }

    settings_data.initialize(date_joined);

    // The emoji module must be initialized before the right sidebar
    // module, so that we can display custom emoji in statuses.
    emoji.initialize({
        realm_emoji: emoji_params.realm_emoji,
        emoji_codes: generated_emoji_codes,
    });

    // These components must be initialized early, because other
    // modules' initialization has not been audited for whether they
    // expect DOM elements to always exist (As that did before these
    // modules were migrated from Django templates to handlebars).
    initialize_left_sidebar();
    initialize_right_sidebar();
    initialize_compose_box();
    settings.initialize();
    initialize_navbar();
    initialize_message_feed_errors();
    realm_logo.render();

    message_lists.initialize();
    alert_words.initialize(alert_words_params);
    emojisets.initialize();
    scroll_bar.initialize();
    message_viewport.initialize();
    navbar_alerts.initialize();
    compose_closed_ui.initialize();
    initialize_kitchen_sink_stuff();
    echo.initialize();
    stream_edit.initialize();
    stream_edit_subscribers.initialize();
    stream_data.initialize(stream_data_params);
    pm_conversations.recent.initialize(pm_conversations_params);
    muted_topics.initialize();
    muted_users.initialize();
    stream_settings_ui.initialize();
    stream_list.initialize();
    condense.initialize();
    spoilers.initialize();
    lightbox.initialize();
    click_handlers.initialize();
    copy_and_paste.initialize();
    overlays.initialize();
    invite.initialize();
    timerender.initialize();
    message_view_header.initialize();
    server_events.initialize();
    user_status.initialize(user_status_params);
    compose_pm_pill.initialize();
    search_pill_widget.initialize();
    reload.initialize();
    user_groups.initialize(user_groups_params);
    unread.initialize();
    bot_data.initialize(bot_params); // Must happen after people.initialize()
    message_fetch.initialize(server_events.home_view_loaded);
    message_scroll.initialize();
    markdown.initialize(markdown_config.get_helpers());
    linkifiers.initialize(page_params.realm_linkifiers);
    realm_playground.initialize(page_params.realm_playgrounds, generated_pygments_data);
    compose.initialize();
    composebox_typeahead.initialize(); // Must happen after compose.initialize()
    search.initialize();
    tutorial.initialize();
    notifications.initialize();
    gear_menu.initialize();
    giphy.initialize();
    presence.initialize(presence_params);
    settings_display.initialize();
    settings_notifications.initialize();
    settings_realm_user_settings_defaults.initialize();
    settings_panel_menu.initialize();
    settings_sections.initialize();
    settings_toggle.initialize();
    about_zulip.initialize();

    // All overlays must be initialized before hashchange.js
    hashchange.initialize();
    resize.initialize();

    unread_ui.initialize();
    activity.initialize();
    emoji_picker.initialize();
    topic_list.initialize();
    topic_zoom.initialize();
    drafts.initialize();
    sent_messages.initialize();
    hotspots.initialize();
    ui.initialize();
    typing.initialize();
    starred_messages.initialize();
    user_status_ui.initialize();
    fenced_code.initialize(generated_pygments_data);
    message_edit_history.initialize();

    $("#app-loading").addClass("loaded");
}

$(() => {
    blueslip.measure_time("initialize_everything", () => {
        initialize_everything();
    });
});
