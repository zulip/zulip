import ClipboardJS from "clipboard";
import {parseISO} from "date-fns";
import $ from "jquery";
import tippy from "tippy.js";

import render_no_arrow_popover from "../templates/no_arrow_popover.hbs";
import render_user_card_popover_content from "../templates/user_card_popover_content.hbs";
import render_user_card_popover_manage_menu from "../templates/user_card_popover_manage_menu.hbs";
import render_user_card_popover_title from "../templates/user_card_popover_title.hbs";

import * as blueslip from "./blueslip";
import * as buddy_data from "./buddy_data";
import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as dialog_widget from "./dialog_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as message_lists from "./message_lists";
import * as muted_users from "./muted_users";
import * as muted_users_ui from "./muted_users_ui";
import * as narrow from "./narrow";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popovers from "./popovers";
import {
    focus_first_popover_item,
    hide_all,
    hide_all_except_sidebars,
    popover_items_handle_keyboard,
} from "./popovers";
import * as rows from "./rows";
import * as settings_config from "./settings_config";
import * as settings_users from "./settings_users";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as user_profile from "./user_profile";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_status_ui from "./user_status_ui";

let $current_message_user_card_popover_elem;
let $current_user_card_popover_elem;
let $current_user_card_popover_manage_menu;
let current_user_sidebar_popover;
let current_user_sidebar_user_id;

let userlist_placement = "right";

export function hide_all_user_card_popovers() {
    hide_user_card_popover_manage_menu();
    hide_message_user_card_popover();
    hide_user_sidebar_popover();
    hide_user_card_popover();
}

export function clear_for_testing() {
    $current_message_user_card_popover_elem = undefined;
    $current_user_card_popover_elem = undefined;
    $current_user_card_popover_manage_menu = undefined;
    userlist_placement = "right";
}

export function elem_to_user_id($elem) {
    return Number.parseInt($elem.attr("data-user-id"), 10);
}

function clipboard_enable(arg) {
    // arg is a selector or element
    // We extract this function for testing purpose.
    return new ClipboardJS(arg);
}

// Functions related to user card popover.

export function toggle_user_card_popover(element, user) {
    const $last_popover_elem = $current_user_card_popover_elem;
    hide_all();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        return;
    }
    const $elt = $(element);
    render_user_card_popover(
        user,
        $elt,
        false,
        false,
        "compose_private_message",
        "user-card-popover",
        "right",
    );
    $current_user_card_popover_elem = $elt;
}

export function hide_user_card_popover() {
    if (is_user_card_open()) {
        $current_user_card_popover_elem.popover("destroy");
        $current_user_card_popover_elem = undefined;
    }
}

export function is_user_card_open() {
    return $current_user_card_popover_elem !== undefined;
}

export function user_card_popover_handle_keyboard(key) {
    const $items = get_user_card_popover_items();
    popover_items_handle_keyboard(key, $items);
}

function get_user_card_popover_items() {
    const $popover_elt = $("div.user-card-popover");
    if (!$current_user_card_popover_elem || !$popover_elt.length) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    if ($popover_elt.length >= 2) {
        blueslip.error("More than one user info popovers cannot be opened at same time.");
        return undefined;
    }

    return $("li:not(.divider):visible a", $popover_elt);
}

function get_user_card_popover_data(
    user,
    has_message_context,
    is_sender_popover,
    private_msg_class,
) {
    const is_me = people.is_my_user_id(user.user_id);

    let invisible_mode = false;

    if (is_me) {
        invisible_mode = !user_settings.presence_enabled;
    }

    const is_active = people.is_active_user_for_popover(user.user_id);
    const is_system_bot = user.is_system_bot;
    const status_text = user_status.get_status_text(user.user_id);
    const status_emoji_info = user_status.get_status_emoji(user.user_id);
    const spectator_view = page_params.is_spectator;

    const show_manage_menu = !spectator_view && !is_me;

    let date_joined;

    // Some users might not have `date_joined` field because of the missing server data.
    // These users are added late in `people.js` via `extract_people_from_message`.
    if (spectator_view && !user.is_missing_server_data) {
        date_joined = timerender.get_localized_date_or_time_for_format(
            parseISO(user.date_joined),
            "dayofyear_year",
        );
    }
    // Filtering out only those profile fields that can be display in the popover and are not empty.
    const field_types = page_params.custom_profile_field_types;
    const display_profile_fields = page_params.custom_profile_fields
        .map((f) => user_profile.get_custom_profile_field_data(user, f, field_types))
        .filter((f) => f.display_in_profile_summary && f.value !== undefined && f.value !== null);

    const args = {
        invisible_mode,
        can_send_private_message:
            is_active &&
            !is_me &&
            page_params.realm_private_message_policy !==
                settings_config.private_message_policy_values.disabled.code,
        display_profile_fields,
        has_message_context,
        is_active,
        is_bot: user.is_bot,
        is_me,
        is_sender_popover,
        pm_with_url: hash_util.pm_with_url(user.email),
        user_circle_class: buddy_data.get_user_circle_class(user.user_id),
        private_message_class: private_msg_class,
        sent_by_url: hash_util.by_sender_url(user.email),
        show_manage_menu,
        user_email: user.delivery_email,
        user_full_name: user.full_name,
        user_id: user.user_id,
        user_last_seen_time_status: buddy_data.user_last_seen_time_status(user.user_id),
        user_time: people.get_user_time(user.user_id),
        user_type: people.get_user_type(user.user_id),
        status_content_available: Boolean(status_text || status_emoji_info),
        status_text,
        status_emoji_info,
        user_mention_syntax: people.get_mention_syntax(user.full_name, user.user_id),
        date_joined,
        spectator_view,
    };

    if (user.is_bot) {
        const bot_owner_id = user.bot_owner_id;
        if (is_system_bot) {
            args.is_system_bot = is_system_bot;
        } else if (bot_owner_id) {
            const bot_owner = people.get_by_user_id(bot_owner_id);
            args.bot_owner = bot_owner;
        }
    }

    return args;
}

function render_user_card_popover(
    user,
    $popover_element,
    is_sender_popover,
    has_message_context,
    private_msg_class,
    template_class,
    popover_placement,
) {
    const args = get_user_card_popover_data(
        user,
        has_message_context,
        is_sender_popover,
        private_msg_class,
    );

    const $popover_content = $(render_user_card_popover_content(args));
    $popover_element.popover({
        content: $popover_content.get(0),
        fixed: true,
        placement: popover_placement,
        template: render_no_arrow_popover({class: template_class}),
        title: render_user_card_popover_title({
            // See the load_medium_avatar comment for important background.
            user_avatar: people.small_avatar_url_for_person(user),
            user_is_guest: user.is_guest,
        }),
        html: true,
        trigger: "manual",
        top_offset: $("#userlist-title").get_offset_to_window().top + 15,
        fix_positions: true,
    });
    $popover_element.popover("show");

    init_email_clipboard();
    init_email_tooltip(user);
    const $user_name_element = $popover_content.find(".user_full_name");
    const $bot_owner_element = $popover_content.find(".bot_owner");
    if ($user_name_element.prop("clientWidth") < $user_name_element.prop("scrollWidth")) {
        $user_name_element.addClass("tippy-zulip-tooltip");
    }
    if (
        args.bot_owner &&
        $bot_owner_element.prop("clientWidth") < $bot_owner_element.prop("scrollWidth")
    ) {
        $bot_owner_element.addClass("tippy-zulip-tooltip");
    }

    // Note: We pass the normal-size avatar in initial rendering, and
    // then query the server to replace it with the medium-size
    // avatar.  The purpose of this double-fetch approach is to take
    // advantage of the fact that the browser should already have the
    // low-resolution image cached and thus display a low-resolution
    // avatar rather than a blank area during the network delay for
    // fetching the medium-size one.
    load_medium_avatar(user, $(".popover-avatar"));
}

function copy_email_handler(e) {
    const $email_el = $(e.trigger.parentElement);
    const $copy_icon = $email_el.find("i");

    // only change the parent element's text back to email
    // and not overwrite the tooltip.
    const email_textnode = $email_el[0].childNodes[2];

    $email_el.addClass("email_copied");
    email_textnode.nodeValue = $t({defaultMessage: "Email copied"});

    setTimeout(() => {
        $email_el.removeClass("email_copied");
        email_textnode.nodeValue = $copy_icon.attr("data-clipboard-text");
    }, 1500);
    e.clearSelection();
}

function init_email_clipboard() {
    /*
        This shows (and enables) the copy-text icon for folks
        who have names that would overflow past the right
        edge of our user mention popup.
    */
    $(".user_popover_email").each(function () {
        if (this.clientWidth < this.scrollWidth) {
            const $email_el = $(this);
            const $copy_email_icon = $email_el.find("i");

            /*
                For deactivated users, the copy-email icon will
                not even be present in the HTML, so we don't do
                anything.  We don't reveal emails for deactivated
                users.
            */
            if ($copy_email_icon[0]) {
                $copy_email_icon.removeClass("hide_copy_icon");
                const copy_email_clipboard = clipboard_enable($copy_email_icon[0]);
                copy_email_clipboard.on("success", copy_email_handler);
            }
        }
    });
}

function init_email_tooltip(user) {
    /*
        This displays the email tooltip for folks
        who have names that would overflow past the right
        edge of our user mention popup.
    */

    $(".user_popover_email").each(function () {
        if (this.clientWidth < this.scrollWidth) {
            tippy(this, {
                placement: "bottom",
                content: people.get_visible_email(user),
                interactive: true,
            });
        }
    });
}

function load_medium_avatar(user, $elt) {
    const user_avatar_url = people.medium_avatar_url_for_person(user);
    const sender_avatar_medium = new Image();

    sender_avatar_medium.src = user_avatar_url;
    $(sender_avatar_medium).on("load", function () {
        $elt.css("background-image", "url(" + $(this).attr("src") + ")");
    });
}

// Functions related to manage menu popover.

function toggle_user_card_popover_manage_menu(element, user) {
    const $last_popover_elem = $current_user_card_popover_manage_menu;
    hide_user_card_popover_manage_menu();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        return;
    }

    const is_me = people.is_my_user_id(user.user_id);
    const is_muted = muted_users.is_user_muted(user.user_id);
    const is_system_bot = user.is_system_bot;
    const muting_allowed = !is_me;

    const args = {
        can_mute: muting_allowed && !is_muted,
        can_manage_user: page_params.is_admin && !is_me && !is_system_bot,
        can_unmute: muting_allowed && is_muted,
        is_active: people.is_active_user_for_popover(user.user_id),
        is_bot: user.is_bot,
        user_id: user.user_id,
    };

    const $popover_elt = $(element);
    $popover_elt.popover({
        content: render_user_card_popover_manage_menu(args),
        placement: "bottom",
        html: true,
        trigger: "manual",
        fixed: true,
    });

    $popover_elt.popover("show");
    $current_user_card_popover_manage_menu = $popover_elt;
}

export function hide_user_card_popover_manage_menu() {
    if ($current_user_card_popover_manage_menu !== undefined) {
        $current_user_card_popover_manage_menu.popover("destroy");
        $current_user_card_popover_manage_menu = undefined;
    }
}

export function is_user_card_manage_menu_open() {
    return $current_user_card_popover_manage_menu !== undefined;
}

export function user_card_popover_manage_menu_handle_keyboard(key) {
    const $items = get_user_card_popover_manage_menu_items();
    popover_items_handle_keyboard(key, $items);
}

export function get_user_card_popover_manage_menu_items() {
    if (!$current_user_card_popover_manage_menu) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = $current_user_card_popover_manage_menu.data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for actions menu.");
        return undefined;
    }

    return $(".user-card-popover-manage-menu li:not(.divider):visible a", popover_data.$tip);
}

// Functions related to message user card popover.

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function toggle_user_card_popover_for_message(element, user, message) {
    const $last_popover_elem = $current_message_user_card_popover_elem;
    hide_all();
    if ($last_popover_elem !== undefined && $last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    message_lists.current.select_id(message.id);
    const $elt = $(element);
    if ($elt.data("popover") === undefined) {
        if (user === undefined) {
            // This is never supposed to happen, not even for deactivated
            // users, so we'll need to debug this error if it occurs.
            blueslip.error("Bad sender in message", {
                zid: message.id,
                sender_id: message.sender_id,
            });
            return;
        }

        const is_sender_popover = message.sender_id === user.user_id;
        render_user_card_popover(
            user,
            $elt,
            is_sender_popover,
            true,
            "respond_personal_button",
            "message-user-card-popover",
            "right",
        );

        $current_message_user_card_popover_elem = $elt;
    }
}

// This function serves as the entry point for toggling
// the user card popover via keyboard shortcut.
export function toggle_sender_info() {
    const $message = $(".selected_message");
    let $sender = $message.find(".message-avatar");
    if ($sender.length === 0) {
        // Messages without an avatar have an invisible message_sender
        // element that's roughly in the right place.
        $sender = $message.find(".message_sender");
    }

    const message = message_lists.current.get(rows.id($message));
    const user = people.get_by_user_id(message.sender_id);
    toggle_user_card_popover_for_message($sender[0], user, message);
    if ($current_message_user_card_popover_elem && !page_params.is_spectator) {
        focus_user_card_popover_item();
    }
}

function focus_user_card_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_user_card_popover_for_message_items();

    if ($(".user-card-popover-manage-menu-btn").is(":visible")) {
        focus_first_popover_item($items, 1);
    } else {
        focus_first_popover_item($items);
    }
}

export function is_message_user_card_open() {
    return $current_message_user_card_popover_elem !== undefined;
}

export function hide_message_user_card_popover() {
    if (is_message_user_card_open()) {
        $current_message_user_card_popover_elem.popover("destroy");
        $current_message_user_card_popover_elem = undefined;
    }
}

export function user_card_popover_for_message_handle_keyboard(key) {
    const $items = get_user_card_popover_for_message_items();
    popover_items_handle_keyboard(key, $items);
}

function get_user_card_popover_for_message_items() {
    if (!$current_message_user_card_popover_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = $current_message_user_card_popover_elem.data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for actions menu.");
        return undefined;
    }

    return $("li:not(.divider):visible a", popover_data.$tip);
}

// Functions related to the user card popover in the user sidebar.

export function user_sidebar_popped() {
    return current_user_sidebar_popover !== undefined;
}

export function hide_user_sidebar_popover() {
    if (user_sidebar_popped()) {
        // this hide_* method looks different from all the others since
        // the presence list may be redrawn. Due to funkiness with jQuery's .data()
        // this would confuse $.popover("destroy"), which looks at the .data() attached
        // to a certain element. We thus save off the .data("popover") in the
        // toggle_user_sidebar_popover and inject it here before calling destroy.
        $("#user_presences").data("popover", current_user_sidebar_popover);
        $("#user_presences").popover("destroy");
        current_user_sidebar_user_id = undefined;
        current_user_sidebar_popover = undefined;
    }
}

function get_user_sidebar_popover_items() {
    if (!current_user_sidebar_popover) {
        blueslip.error("Trying to get menu items when user sidebar popover is closed.");
        return undefined;
    }

    return $("li:not(.divider):visible a", current_user_sidebar_popover.$tip);
}

export function user_sidebar_popover_handle_keyboard(key) {
    const $items = get_user_sidebar_popover_items();
    popover_items_handle_keyboard(key, $items);
}

export function register_click_handlers() {
    $("#main_div").on("click", ".sender_name, .message-avatar", function (e) {
        const $row = $(this).closest(".message_row");
        e.stopPropagation();
        const message = message_lists.current.get(rows.id($row));
        const user = people.get_by_user_id(message.sender_id);
        toggle_user_card_popover_for_message(this, user, message);
    });

    $("#main_div").on("click", ".user-mention", function (e) {
        const id_string = $(this).attr("data-user-id");
        // We fallback to email to handle legacy Markdown that was rendered
        // before we cut over to using data-user-id
        const email = $(this).attr("data-user-email");
        if (id_string === "*" || email === "*") {
            return;
        }
        const $row = $(this).closest(".message_row");
        e.stopPropagation();
        const message = message_lists.current.get(rows.id($row));
        let user;
        if (id_string) {
            const user_id = Number.parseInt(id_string, 10);
            user = people.get_by_user_id(user_id);
        } else {
            user = people.get_by_email(email);
        }
        toggle_user_card_popover_for_message(this, user, message);
    });

    $("body").on("click", ".user-card-popover-actions .narrow_to_private_messages", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        hide_all();
        if (overlays.is_active()) {
            overlays.close_active();
        }
        narrow.by("dm", email, {trigger: "user sidebar popover"});
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".user-card-popover-actions .narrow_to_messages_sent", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        hide_all();
        if (overlays.is_active()) {
            overlays.close_active();
        }
        narrow.by("sender", email, {trigger: "user sidebar popover"});
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".user-card-popover-actions .clear_status", (e) => {
        e.preventDefault();
        const me = elem_to_user_id($(e.target).parents("ul"));
        user_status.server_update_status({
            user_id: me,
            status_text: "",
            emoji_name: "",
            emoji_code: "",
            success() {
                $(".user-card-popover-actions #status_message").empty();
            },
        });
    });

    $("body").on("click", ".user-card-popover-actions .sidebar-popover-reactivate-user", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        hide_all();
        e.stopPropagation();
        e.preventDefault();
        function handle_confirm() {
            const url = "/json/users/" + encodeURIComponent(user_id) + "/reactivate";
            channel.post({
                url,
                success() {
                    dialog_widget.close_modal();
                },
                error(xhr) {
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }
        settings_users.confirm_reactivation(user_id, handle_confirm, true);
    });

    $("body").on("click", ".user-card-popover-actions .view_full_user_profile", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user);
        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".user_popover .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_actions.start("stream", {trigger: "sidebar user actions"});
        }
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        hide_user_sidebar_popover();
        popovers.hide_userlist_sidebar();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".message-user-card-popover .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_actions.respond_to_message({trigger: "user sidebar popover"});
        }
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        hide_message_user_card_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".view_user_profile", (e) => {
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const user = people.get_by_user_id(user_id);
        toggle_user_card_popover(e.target, user);
        e.stopPropagation();
        e.preventDefault();
    });

    /* These click handlers are implemented as just deep links to the
     * relevant part of the Zulip UI, so we don't want preventDefault,
     * but we do want to close the modal when you click them. */

    $("body").on("click", ".invisible_mode_turn_on", (e) => {
        hide_all();
        user_status.server_invisible_mode_on();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".invisible_mode_turn_off", (e) => {
        hide_all();
        user_status.server_invisible_mode_off();
        e.stopPropagation();
        e.preventDefault();
    });

    function open_user_status_modal(e) {
        hide_all();

        user_status_ui.open_user_status_modal();

        e.stopPropagation();
        e.preventDefault();
    }

    $("body").on("click", ".update_status_text", open_user_status_modal);

    // Clicking on one's own status emoji should open the user status modal.
    $("#user_presences").on(
        "click",
        ".user_sidebar_entry_me .status-emoji",
        open_user_status_modal,
    );

    $("#user_presences").on("click", ".user-list-sidebar-menu-icon", function (e) {
        e.stopPropagation();

        const $target = $(this).closest("li");
        const user_id = elem_to_user_id($target.find("a"));
        // Hiding popovers may mutate current_user_sidebar_user_id.
        const previous_user_sidebar_id = current_user_sidebar_user_id;

        // Hide popovers, but we don't want to hide the sidebars on
        // smaller browser windows.
        hide_all_except_sidebars();

        if (previous_user_sidebar_id === user_id) {
            // If the popover is already shown, clicking again should toggle it.
            return;
        }

        const user = people.get_by_user_id(user_id);
        const popover_placement = userlist_placement === "left" ? "right" : "left";

        render_user_card_popover(
            user,
            $target,
            false,
            false,
            "compose_private_message",
            "user_popover",
            popover_placement,
        );

        current_user_sidebar_user_id = user.user_id;
        current_user_sidebar_popover = $target.data("popover");
    });

    $("body").on("click", ".sidebar-popover-mute-user", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        hide_all_user_card_popovers();
        e.stopPropagation();
        e.preventDefault();
        muted_users_ui.confirm_mute_user(user_id);
    });

    $("body").on("click", ".sidebar-popover-unmute-user", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        hide_all_user_card_popovers();
        muted_users_ui.unmute_user(user_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".respond_personal_button, .compose_private_message", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        compose_actions.start("private", {
            trigger: "popover send private",
            private_message_recipient: email,
        });
        hide_all();
        if (overlays.is_active()) {
            overlays.close_active();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".copy_mention_syntax", (e) => {
        hide_all();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".sidebar-popover-manage-user", (e) => {
        hide_all();
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user, "manage-profile-tab");
    });

    $("body").on("click", ".user-card-popover-manage-menu-btn", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        toggle_user_card_popover_manage_menu(e.target, user);
    });
}

export function initialize() {
    register_click_handlers();
    clipboard_enable(".copy_mention_syntax");
}
