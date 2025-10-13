import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";

import generated_emoji_codes from "../../static/generated/emoji/emoji_codes.json";
import render_compose from "../templates/compose.hbs";
import render_message_feed_errors from "../templates/message_feed_errors.hbs";
import render_navbar from "../templates/navbar.hbs";
import render_try_zulip_modal from "../templates/try_zulip_modal.hbs";
import render_view_bottom_loading_indicator from "../templates/view_bottom_loading_indicator.hbs";

import * as about_zulip from "./about_zulip.ts";
import * as activity from "./activity.ts";
import * as activity_ui from "./activity_ui.ts";
import * as add_stream_options_popover from "./add_stream_options_popover.ts";
import * as alert_words from "./alert_words.ts";
import {all_messages_data} from "./all_messages_data.ts";
import * as audible_notifications from "./audible_notifications.ts";
import * as banners from "./banners.ts";
import * as blueslip from "./blueslip.ts";
import * as bot_data from "./bot_data.ts";
import * as channel from "./channel.ts";
import * as channel_folders from "./channel_folders.ts";
import * as channel_folders_popover from "./channel_folders_popover.ts";
import * as click_handlers from "./click_handlers.ts";
import * as color_picker_popover from "./color_picker_popover.ts";
import * as common from "./common.ts";
import * as compose from "./compose.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as compose_notifications from "./compose_notifications.ts";
import * as compose_paste from "./compose_paste.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_reply from "./compose_reply.ts";
import * as compose_send_menu_popover from "./compose_send_menu_popover.ts";
import * as compose_setup from "./compose_setup.ts";
import * as compose_textarea from "./compose_textarea.ts";
import * as compose_tooltips from "./compose_tooltips.ts";
import * as compose_validate from "./compose_validate.ts";
import * as composebox_typeahead from "./composebox_typeahead.ts";
import * as condense from "./condense.ts";
import * as copy_messages from "./copy_messages.ts";
import * as desktop_integration from "./desktop_integration.ts";
import * as desktop_notifications from "./desktop_notifications.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as drafts from "./drafts.ts";
import * as drafts_overlay_ui from "./drafts_overlay_ui.ts";
import * as echo from "./echo.ts";
import * as emoji from "./emoji.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as emojisets from "./emojisets.ts";
import * as fenced_code from "./fenced_code.ts";
import * as gear_menu from "./gear_menu.ts";
import * as gif_state from "./gif_state.ts";
import * as giphy from "./giphy.ts";
import * as group_permission_settings from "./group_permission_settings.ts";
import * as hashchange from "./hashchange.ts";
import * as hotkey from "./hotkey.ts";
import * as i18n from "./i18n.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as information_density from "./information_density.ts";
import * as invite from "./invite.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as left_sidebar_navigation_area_popovers from "./left_sidebar_navigation_area_popovers.ts";
import * as left_sidebar_tooltips from "./left_sidebar_tooltips.ts";
import * as lightbox from "./lightbox.ts";
import * as linkifiers from "./linkifiers.ts";
import * as local_message from "./local_message.ts";
import * as markdown from "./markdown.ts";
import * as markdown_config from "./markdown_config.ts";
import * as message_actions_popover from "./message_actions_popover.ts";
import * as message_edit_history from "./message_edit_history.ts";
import * as message_fetch from "./message_fetch.ts";
import * as message_list_hover from "./message_list_hover.ts";
import * as message_list_tooltips from "./message_list_tooltips.ts";
import * as message_lists from "./message_lists.ts";
import * as message_reminder from "./message_reminder.ts";
import * as message_scroll from "./message_scroll.ts";
import * as message_view from "./message_view.ts";
import * as message_view_header from "./message_view_header.ts";
import * as message_viewport from "./message_viewport.ts";
import * as modals from "./modals.ts";
import * as mouse_drag from "./mouse_drag.ts";
import * as muted_users from "./muted_users.ts";
import * as narrow_history from "./narrow_history.ts";
import * as narrow_state from "./narrow_state.ts";
import * as narrow_title from "./narrow_title.ts";
import * as navbar_alerts from "./navbar_alerts.ts";
import * as navbar_help_menu from "./navbar_help_menu.ts";
import * as navigate from "./navigate.ts";
import * as navigation_views from "./navigation_views.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as personal_menu_popover from "./personal_menu_popover.ts";
import * as playground_links_popover from "./playground_links_popover.ts";
import * as pm_conversations from "./pm_conversations.ts";
import * as pm_list from "./pm_list.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import * as popup_banners from "./popup_banners.ts";
import * as presence from "./presence.ts";
import * as pygments_data from "./pygments_data.ts";
import * as realm_logo from "./realm_logo.ts";
import * as realm_playground from "./realm_playground.ts";
import * as realm_user_settings_defaults from "./realm_user_settings_defaults.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as reload_setup from "./reload_setup.ts";
import * as reminders_overlay_ui from "./reminders_overlay_ui.ts";
import * as resize_handler from "./resize_handler.ts";
import * as saved_snippets from "./saved_snippets.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as scheduled_messages_overlay_ui from "./scheduled_messages_overlay_ui.ts";
import * as scheduled_messages_ui from "./scheduled_messages_ui.ts";
import * as scroll_bar from "./scroll_bar.ts";
import * as scroll_util from "./scroll_util.ts";
import * as search from "./search.ts";
import * as server_events from "./server_events.js";
import * as server_events_state from "./server_events_state.ts";
import * as settings from "./settings.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_panel_menu from "./settings_panel_menu.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults.ts";
import * as settings_sections from "./settings_sections.ts";
import * as settings_toggle from "./settings_toggle.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as spoilers from "./spoilers.ts";
import * as starred_messages from "./starred_messages.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import {
    current_user,
    realm,
    set_current_user,
    set_realm,
    set_realm_billing,
    state_data_schema,
} from "./state_data.ts";
import * as stream_card_popover from "./stream_card_popover.ts";
import * as stream_create from "./stream_create.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_edit from "./stream_edit.ts";
import * as stream_edit_subscribers from "./stream_edit_subscribers.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_list_sort from "./stream_list_sort.ts";
import * as stream_popover from "./stream_popover.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_topic_history_util from "./stream_topic_history_util.ts";
import * as sub_store from "./sub_store.ts";
import * as theme from "./theme.ts";
import * as thumbnail from "./thumbnail.ts";
import * as timerender from "./timerender.ts";
import * as tippyjs from "./tippyjs.ts";
import * as topic_list from "./topic_list.ts";
import * as topic_popover from "./topic_popover.ts";
import * as transmit from "./transmit.ts";
import * as typeahead_helper from "./typeahead_helper.ts";
import * as typing from "./typing.ts";
import * as unread from "./unread.ts";
import * as unread_ops from "./unread_ops.ts";
import * as unread_ui from "./unread_ui.ts";
import * as upload from "./upload.ts";
import * as user_card_popover from "./user_card_popover.ts";
import * as user_group_edit from "./user_group_edit.ts";
import * as user_group_edit_members from "./user_group_edit_members.ts";
import * as user_group_popover from "./user_group_popover.ts";
import * as user_groups from "./user_groups.ts";
import * as user_profile from "./user_profile.ts";
import {initialize_user_settings, user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import * as user_status_ui from "./user_status_ui.ts";
import * as user_topic_popover from "./user_topic_popover.ts";
import * as user_topics from "./user_topics.ts";
import * as util from "./util.ts";
import * as widgets from "./widgets.ts";

// This is where most of our initialization takes place.
// TODO: Organize it a lot better.  In particular, move bigger
//       functions to other modules.

/* We use 'visibility' rather than 'display' and jQuery's show() / hide(),
   because we want to reserve space for the email address.  This avoids
   things jumping around slightly when the email address is shown. */

function initialize_bottom_whitespace() {
    $("#bottom_whitespace").html(render_view_bottom_loading_indicator());
}

function initialize_navbar() {
    const rendered_navbar = render_navbar({
        embedded: page_params.narrow_stream !== undefined,
        user_avatar: current_user.avatar_url_medium,
        realm_icon_url: realm.realm_icon_url,
    });

    $("#header-container").html(rendered_navbar);
    // Track when the image is loaded to updated CSS properties.
    $("#header-container img.header-button-avatar-image").on("load", (e) => {
        e.currentTarget.classList.add("avatar-loaded");
    });
}

function initialize_compose_box() {
    $("#compose-container").append(
        $(
            render_compose({
                embedded: $("#compose").attr("data-embedded") === "",
                file_upload_enabled: realm.max_file_upload_size_mib > 0 && upload.feature_check(),
                giphy_enabled: gif_state.is_giphy_enabled(),
                max_stream_name_length: realm.max_stream_name_length,
                max_topic_length: realm.max_topic_length,
                empty_string_topic_display_name: util.get_final_topic_display_name(""),
            }),
        ),
    );
    $(`.enter_sends_${user_settings.enter_sends}`).show();
    common.adjust_mac_kbd_tags(".open_enter_sends_dialog kbd");
}

function initialize_message_feed_errors() {
    $("#message_feed_errors_container").html(
        render_message_feed_errors({
            is_guest: current_user.is_guest,
        }),
    );
}

export function initialize_kitchen_sink_stuff() {
    // TODO:
    //      This function is a historical dumping ground
    //      for lots of miscellaneous setup.  Almost all of
    //      the code here can probably be moved to more
    //      specific-purpose modules like message_viewport.ts.

    const throttled_mousewheelhandler = _.throttle((_e, delta) => {
        if (!narrow_state.is_message_feed_visible()) {
            // Since this function is called with a delay, it's
            // possible that message list was hidden before we reached here.
            return;
        }

        // Most of the mouse wheel's work will be handled by the
        // scroll handler, but when we're at the top or bottom of the
        // page, the pointer may still need to move.

        if (delta < 0 && message_viewport.at_rendered_top()) {
            navigate.up();
        } else if (delta > 0 && message_viewport.at_rendered_bottom()) {
            navigate.down();
        }

        message_viewport.set_last_movement_direction(delta);
    }, 50);

    message_viewport.$scroll_container.on("wheel", (e) => {
        const delta = e.originalEvent.deltaY;
        if (
            !popovers.any_active() &&
            !overlays.any_active() &&
            !modals.any_active() &&
            narrow_state.is_message_feed_visible()
        ) {
            // In the message view, we use a throttled mousewheel handler.
            throttled_mousewheelhandler(e, delta);
        }
        // If in a modal, we neither handle the event nor
        // preventDefault, allowing the modal to scroll normally.
    });

    $(window).on("resize", _.throttle(resize_handler.handler, 50));

    // Scrolling in overlays. input boxes, and other elements that
    // explicitly scroll should not scroll the main view.  Stop
    // propagation in all cases.  Also, ignore the event if the
    // element is already at the top or bottom.  Otherwise we get a
    // new scroll event on the parent (?).
    $(".overlay-scroll-container, .scrolling_list, input, textarea").on("wheel", function (e) {
        const $self = scroll_util.get_scroll_element($(this));
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
        // Except for the compose banners or formatting buttons,
        // which still need scroll events.
        if (
            $(e.target).closest("#compose_banners, #message-formatting-controls-container").length >
            0
        ) {
            return;
        }
        e.stopPropagation();
        e.preventDefault();
    });

    // A little hackish, because it doesn't seem to totally get us the
    // exact right width for the compose box, but, close enough for now.
    resize_handler.handler();

    if (page_params.is_spectator) {
        $("body").addClass("spectator-view");
    }

    if (user_settings.high_contrast_mode) {
        $("body").addClass("high-contrast");
    }

    $(window).on("blur", () => {
        $(document.body).addClass("window_blurred");
    });

    $(window).on("focus", () => {
        $(document.body).removeClass("window_blurred");
    });

    $(document).on("message_selected.zulip", (event) => {
        if (message_lists.current === undefined || message_lists.current !== event.msg_list) {
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
                            .toSorted(),
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

        // Save selected message and scroll position after we have scrolled to it.
        narrow_history.save_narrow_state();
    });

    if (!realm.realm_allow_message_editing) {
        $("#edit-message-hotkey-help").hide();
    }

    if (realm.realm_presence_disabled) {
        $("#user-list").hide();
    }
}

function initialize_unread_ui() {
    unread_ui.register_update_unread_counts_hook((counts) =>
        activity_ui.update_dom_with_unread_counts(counts),
    );
    unread_ui.register_update_unread_counts_hook((counts, skip_animations) =>
        left_sidebar_navigation_area.update_dom_with_unread_counts(counts, skip_animations),
    );
    unread_ui.register_update_unread_counts_hook((counts) =>
        stream_list.update_dom_with_unread_counts(counts),
    );
    unread_ui.register_update_unread_counts_hook((counts) =>
        pm_list.update_dom_with_unread_counts(counts),
    );
    unread_ui.register_update_unread_counts_hook(() => topic_list.update());
    unread_ui.register_update_unread_counts_hook((counts) =>
        narrow_title.update_unread_counts(counts),
    );
    unread_ui.register_update_unread_counts_hook(inbox_ui.update);

    unread_ui.initialize({notify_server_messages_read: unread_ops.notify_server_messages_read});
}

export async function initialize_everything(state_data) {
    /*
        When we initialize our various modules, a lot
        of them will consume data from the server
        in the form of `state_data`.

        The `state_data` variable is basically a
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
        load comes from `state_data`.

        The version of `state_data` that we've been passed has already been
        split using Zod `.transform` invocations into a number of parts; see
        `state_data_schema` in `state_data.ts`. Below we pass each part to the
        initialization function for the corresponding module.
    */

    set_current_user(state_data.current_user);
    set_realm(state_data.realm);
    set_realm_billing(state_data.realm_billing);

    /* To store theme data for spectators, we need to initialize
       user_settings before setting the theme. Because information
       density is so fundamental, we initialize that first, however. */
    initialize_user_settings(state_data.user_settings);
    mouse_drag.initialize();
    sidebar_ui.restore_sidebar_toggle_status();
    i18n.initialize({language_list: page_params.language_list});
    timerender.initialize();
    information_density.initialize();
    if (page_params.is_spectator) {
        theme.initialize_theme_for_spectator();
    }
    thumbnail.initialize();
    widgets.initialize();
    tippyjs.initialize();
    compose_tooltips.initialize();
    message_list_tooltips.initialize();
    left_sidebar_tooltips.initialize();
    // This populates data for scheduled messages.
    scheduled_messages.initialize(state_data.scheduled_messages);
    message_reminder.initialize(state_data.reminders);
    navigation_views.initialize(state_data.navigation_views);
    scheduled_messages_ui.initialize();
    reminders_overlay_ui.initialize();
    popover_menus.initialize();
    left_sidebar_navigation_area_popovers.initialize();
    user_topic_popover.initialize();
    topic_popover.initialize();
    const message_reminder_click_handler = (remind_message_id, target) => {
        compose_send_menu_popover.open_schedule_message_menu(remind_message_id, target);
    };
    message_actions_popover.initialize({message_reminder_click_handler});
    compose_send_menu_popover.initialize();

    realm_user_settings_defaults.initialize(state_data.realm_settings_defaults);

    // The user_group must be initialized before right sidebar
    // module, so that we can tell whether user is member of
    // user_group whose members are allowed to create multiuse
    // invite. The user_group module must also be initialized
    // before people module, so that can_access_all_users_group
    // setting group can be used to check whether the user
    // has permission to access all other users.
    user_groups.initialize(state_data.user_groups);

    await people.initialize(current_user.user_id, state_data.people, state_data.user_groups);
    starred_messages.initialize(state_data.starred_messages);

    // The emoji module must be initialized before the right sidebar
    // module, so that we can display custom emoji in statuses.
    emoji.initialize({
        ...state_data.emoji,
        emoji_codes: generated_emoji_codes,
    });

    // Channel folders data must be initialized before left sidebar.
    channel_folders.initialize(state_data.channel_folders);

    // These components must be initialized early, because other
    // modules' initialization has not been audited for whether they
    // expect DOM elements to always exist (As that did before these
    // modules were migrated from Django templates to Handlebars).
    initialize_bottom_whitespace();
    sidebar_ui.initialize_left_sidebar();
    sidebar_ui.initialize_right_sidebar();
    initialize_compose_box();
    settings.initialize();
    initialize_navbar();
    initialize_message_feed_errors();

    // Needs to be set before we fetch any messages.
    stream_topic_history.set_update_topic_last_message_id((stream_id, topic_name) => {
        stream_topic_history_util.update_topic_last_message_id(
            stream_id,
            topic_name,
            stream_list.update_streams_sidebar,
        );
    });

    realm_logo.initialize();
    message_lists.initialize();
    // Needs to be initialized before activity to register window.focus event.
    recent_view_ui.initialize({
        on_click_participant(avatar_element, participant_user_id) {
            const user = people.get_by_user_id(participant_user_id);
            user_card_popover.toggle_user_card_popover(avatar_element, user);
        },
        on_mark_pm_as_read: unread_ops.mark_pm_as_read,
        on_mark_topic_as_read: unread_ops.mark_topic_as_read,
        maybe_load_older_messages(first_unread_message_id) {
            recent_view_ui.set_backfill_in_progress(true);
            message_fetch.maybe_load_older_messages({
                msg_list_data: all_messages_data,
                recent_view: true,
                // To have a hard anchor on our target of first unread message id,
                // we pass it from here, otherwise it might get updated and lead to confusion.
                first_unread_message_id,
            });
        },
        hide_other_views: inbox_ui.hide,
    });
    inbox_ui.initialize({
        hide_other_views: recent_view_ui.hide,
    });
    alert_words.initialize(state_data.alert_words);
    saved_snippets.initialize(state_data.saved_snippets);
    emojisets.initialize();
    scroll_bar.initialize();
    message_viewport.initialize();
    banners.initialize();
    navbar_alerts.initialize();
    popup_banners.initialize();
    message_list_hover.initialize();
    initialize_kitchen_sink_stuff();
    local_message.initialize(state_data.local_message);
    echo.initialize({
        on_send_message_success: compose.send_message_success,
        send_message: transmit.send_message,
    });
    stream_create.initialize();
    stream_edit.initialize();
    user_group_edit.initialize();
    stream_edit_subscribers.initialize();
    stream_data.initialize(state_data.stream_data);
    user_group_edit_members.initialize();
    stream_card_popover.initialize();
    pm_conversations.recent.initialize(state_data.pm_conversations);
    user_topics.initialize(state_data.user_topics);
    muted_users.initialize(state_data.muted_users);
    stream_settings_ui.initialize();
    left_sidebar_navigation_area.initialize();
    stream_list_sort.initialize();
    stream_list.initialize({
        show_channel_feed(stream_id, trigger) {
            const sub = sub_store.get(stream_id);
            sidebar_ui.hide_all();
            popovers.hide_all();
            message_view.show(
                [
                    {
                        operator: "stream",
                        operand: sub.stream_id.toString(),
                    },
                ],
                {trigger},
            );
        },
        update_inbox_channel_view: inbox_ui.update_channel_view,
    });
    condense.initialize();
    spoilers.initialize();
    lightbox.initialize();
    sidebar_ui.initialize();
    user_profile.initialize();
    stream_popover.initialize();
    color_picker_popover.initialize();
    add_stream_options_popover.initialize();
    channel_folders_popover.initialize();
    click_handlers.initialize();
    scheduled_messages_overlay_ui.initialize();
    compose_paste.initialize({
        upload_pasted_file: upload.upload_pasted_file,
    });
    overlays.initialize();
    invite.initialize();
    message_view_header.initialize();
    server_events_state.initialize({
        ...state_data.server_events_state,
        assert_get_events_running: server_events.assert_get_events_running,
        restart_get_events: server_events.restart_get_events,
    });
    server_events.initialize(state_data.server_events);
    user_status.initialize(state_data.user_status);
    compose_recipient.initialize();
    compose_pm_pill.initialize({
        on_pill_create_or_remove() {
            compose_recipient.update_compose_area_placeholder_text();
            compose_validate.validate_and_update_send_button_status();
        },
    });
    compose_closed_ui.initialize();
    compose_reply.initialize();
    drafts.initialize(); // Must happen before reload_setup.initialize()
    reload_setup.initialize();
    unread.initialize(state_data.unread);
    bot_data.initialize(state_data.bot); // Must happen after people.initialize()
    message_fetch.initialize(() => {
        recent_view_ui.set_initial_message_fetch_status(false);
        recent_view_ui.revive_current_focus();
        server_events.finished_initial_fetch();
    });
    message_scroll.initialize();
    markdown.initialize(markdown_config.get_helpers());
    linkifiers.initialize(realm.realm_linkifiers);
    realm_playground.initialize({
        playground_data: realm.realm_playgrounds,
        pygments_comparator_func: typeahead_helper.compare_language,
    });
    copy_messages.initialize();
    compose_setup.initialize();
    // Typeahead must be initialized after compose_setup.initialize()
    composebox_typeahead.initialize({
        on_enter_send: compose.finish,
    });
    compose_validate.initialize();
    compose_textarea.initialize();
    upload.initialize();
    search.initialize({
        on_narrow_search: message_view.show,
    });
    desktop_notifications.initialize();
    audible_notifications.initialize();
    compose_notifications.initialize({
        on_click_scroll_to_selected: message_viewport.scroll_to_selected,
        on_narrow_to_recipient(message_id) {
            message_view.narrow_by_topic(message_id, {trigger: "compose_notification"});
        },
    });
    unread_ops.initialize();
    gear_menu.initialize();
    navbar_help_menu.initialize();
    giphy.initialize();
    presence.initialize(state_data.presence);
    settings_preferences.initialize();
    settings_notifications.initialize();
    settings_realm_user_settings_defaults.initialize();
    settings_panel_menu.initialize();
    settings_sections.initialize();
    settings_toggle.initialize();
    about_zulip.initialize();

    initialize_unread_ui();
    activity.initialize();
    activity.register_on_new_user_input_hook(() => {
        // Instead of marking new messages as read immediately when bottom
        // of feed is visible, we wait for user input to mark them as read.
        // This is to prevent marking messages as read unintentionally,
        // especially when user is away from screen and the window is focused.
        if (activity.received_new_messages && activity.new_user_input) {
            unread_ops.process_visible();
            activity.set_received_new_messages(false);
        }
    });
    activity_ui.initialize({
        narrow_by_email(email) {
            message_view.show(
                [
                    {
                        operator: "dm",
                        operand: email,
                    },
                ],
                {trigger: "sidebar"},
            );
        },
    });

    // All overlays, and also activity_ui, must be initialized before hashchange.ts
    hashchange.initialize();

    emoji_picker.initialize();
    user_group_popover.initialize();
    user_card_popover.initialize();
    playground_links_popover.initialize();
    personal_menu_popover.initialize();
    pm_list.initialize();
    topic_list.initialize({
        on_topic_click(stream_id, topic) {
            const sub = sub_store.get(stream_id);
            const latest_msg_id = stream_topic_history.get_latest_known_message_id_in_topic(
                stream_id,
                topic,
            );

            const narrow = [
                {operator: "channel", operand: sub.stream_id.toString()},
                {operator: "topic", operand: topic},
            ];

            if (latest_msg_id !== undefined) {
                narrow.push({operator: "with", operand: String(latest_msg_id)});
            }

            message_view.show(narrow, {trigger: "sidebar"});

            if (sidebar_ui.left_sidebar_expanded_as_overlay) {
                // If the left sidebar is drawn over the center pane,
                // hide it so that the user can actually see the
                // topic. We don't need to also hide the user list
                // sidebar, since its own click-outside handler will
                // hide it.
                sidebar_ui.hide_streamlist_sidebar();
            }
        },
    });
    drafts.initialize_ui();
    drafts_overlay_ui.initialize();
    // This needs to happen after activity_ui.initialize, so that user_filter
    // is defined. Also, must happen after people.initialize()
    onboarding_steps.initialize(state_data.onboarding_steps, {
        show_message_view: message_view.show,
    });
    typing.initialize();
    starred_messages_ui.initialize();
    user_status_ui.initialize();
    fenced_code.initialize(pygments_data);
    message_edit_history.initialize();
    hotkey.initialize();
    desktop_integration.initialize();

    group_permission_settings.initialize();
    overlays.trap_focus_for_settings_overlay();

    $("#app-loading").addClass("loaded");
}

function show_try_zulip_modal() {
    const html_body = render_try_zulip_modal();
    dialog_widget.launch({
        text_heading: i18n.$t({defaultMessage: "Welcome to the Zulip development community!"}),
        html_body,
        html_submit_button: i18n.$t({defaultMessage: "Let's go!"}),
        on_click() {
            // Do nothing
        },
        single_footer_button: true,
        focus_submit_on_open: true,
        close_on_submit: true,
    });
}

$(() => {
    // Remove '?show_try_zulip_modal', if present.
    const url = new URL(window.location.href);
    if (url.searchParams.has("show_try_zulip_modal")) {
        url.searchParams.delete("show_try_zulip_modal");
        window.history.replaceState(window.history.state, "", url.toString());
    }

    if (page_params.is_spectator) {
        const data = {
            apply_markdown: true,
            client_capabilities: JSON.stringify({
                notification_settings_null: true,
                bulk_message_deletion: true,
                user_avatar_url_field_optional: true,
                // Set this to true when stream typing notifications are implemented.
                stream_typing_notifications: false,
                user_settings_object: true,
                empty_topic_name: true,
            }),
            client_gravatar: false,
        };
        channel.post({
            url: "/json/register",
            data,
            success(response_data) {
                const state_data = state_data_schema.parse(response_data);
                initialize_everything(state_data);
                if (page_params.show_try_zulip_modal) {
                    show_try_zulip_modal();
                }
            },
            error() {
                $("#app-loading-middle-content").hide();
                $("#app-loading-bottom-content").hide();
                $(".app").hide();
                $("#app-loading-error").css({visibility: "visible"});
            },
        });
    } else {
        const state_data = page_params.state_data;
        assert(state_data !== null);
        page_params.state_data = null;
        initialize_everything(state_data);
    }
});
