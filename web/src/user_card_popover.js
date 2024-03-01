import ClipboardJS from "clipboard";
import {parseISO} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";
import tippy from "tippy.js";

import render_confirm_mute_user from "../templates/confirm_dialog/confirm_mute_user.hbs";
import render_user_card_popover from "../templates/popovers/user_card/user_card_popover.hbs";
import render_user_card_popover_avatar from "../templates/popovers/user_card/user_card_popover_avatar.hbs";
import render_user_card_popover_for_unknown_user from "../templates/popovers/user_card/user_card_popover_for_unknown_user.hbs";
import render_user_card_popover_manage_menu from "../templates/popovers/user_card/user_card_popover_manage_menu.hbs";

import * as blueslip from "./blueslip";
import * as browser_history from "./browser_history";
import * as buddy_data from "./buddy_data";
import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_reply from "./compose_reply";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import * as confirm_dialog from "./confirm_dialog";
import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import * as hash_util from "./hash_util";
import {$t, $t_html} from "./i18n";
import * as message_lists from "./message_lists";
import * as muted_users from "./muted_users";
import * as narrow from "./narrow";
import * as overlays from "./overlays";
import {page_params} from "./page_params";
import * as people from "./people";
import * as popover_menus from "./popover_menus";
import {hide_all} from "./popovers";
import * as rows from "./rows";
import * as settings_config from "./settings_config";
import * as sidebar_ui from "./sidebar_ui";
import {current_user, realm} from "./state_data";
import * as timerender from "./timerender";
import * as ui_report from "./ui_report";
import * as ui_util from "./ui_util";
import * as user_deactivation_ui from "./user_deactivation_ui";
import * as user_profile from "./user_profile";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_status_ui from "./user_status_ui";

let current_user_sidebar_user_id;

export function confirm_mute_user(user_id) {
    function on_click() {
        muted_users.mute_user(user_id);
    }

    const html_body = render_confirm_mute_user({
        user_name: people.get_full_name(user_id),
    });

    confirm_dialog.launch({
        html_heading: $t_html({defaultMessage: "Mute user"}),
        help_link: "/help/mute-a-user",
        html_body,
        on_click,
    });
}

class PopoverMenu {
    constructor() {
        this.instance = null;
    }

    is_open() {
        return Boolean(this.instance);
    }

    hide() {
        if (this.is_open()) {
            this.instance.destroy();
            this.instance = undefined;
        }
    }

    handle_keyboard(key) {
        if (!this.is_open()) {
            blueslip.error("Trying to get the items when popover is closed.");
            return;
        }

        const $popover = $(this.instance?.popper);
        if (!$popover) {
            blueslip.error("Cannot find popover data.");
            return;
        }

        const $items = $("li:not(.divider):visible a", $popover);

        popover_items_handle_keyboard_with_overrides(key, $items);
    }
}

export const manage_menu = new PopoverMenu();
export const user_sidebar = new PopoverMenu();
export const message_user_card = new PopoverMenu();
export const user_card = new PopoverMenu();

function popover_items_handle_keyboard_with_overrides(key, $items) {
    /* Variant of popover_items_handle_keyboard with somewhat hacky
     * logic for opening the manage menu. */
    if (!$items) {
        return;
    }

    const index = $items.index($items.filter(":focus"));

    if (key === "enter" && index >= 0 && index < $items.length) {
        $items[index].click();
        if (manage_menu.is_open()) {
            // If we just opened the little manage menu via the
            // keyboard, we need to focus the first item for a
            // continuation of the keyboard experience.

            // TODO: This might be cleaner to just call
            // toggle_user_card_popover_manage_menu rather than
            // triggering a click.

            const previously_defined_on_mount = manage_menu.instance.props.onMount;
            manage_menu.instance.setProps({
                onMount() {
                    // We're monkey patching the onMount method here to ensure we start
                    // focusing on the item after the popover is mounted to the DOM;
                    // otherwise, it won't work correctly.
                    if (previously_defined_on_mount) {
                        previously_defined_on_mount();
                    }
                    const $items = get_user_card_popover_manage_menu_items();
                    popover_menus.focus_first_popover_item($items);
                },
            });
        }
        return;
    }

    if (
        index === -1 &&
        $(".user-card-popover-manage-menu-btn").is(":visible") &&
        !manage_menu.is_open()
    ) {
        // If we have a "Manage Menu" button in the user card popover,
        // the first item to receive focus shouldn't be that button.
        // However, if the Manage Menu is open, focus should shift to
        // the first item in that popover.
        const adjusted_index = 1;
        $items.eq(adjusted_index).trigger("focus");
        return;
    }

    /* Otherwise, use the base implementation */
    popover_menus.popover_items_handle_keyboard(key, $items);
}

function get_popover_classname(popover) {
    const popovers = {
        user_sidebar: "user-sidebar-popover-root",
        message_user_card: "message-user-card-popover-root",
        user_card: "user-card-popover-root",
    };

    return popovers[popover];
}

user_sidebar.hide = function () {
    PopoverMenu.prototype.hide.call(this);
    current_user_sidebar_user_id = undefined;
};

const user_card_popovers = {
    manage_menu,
    user_sidebar,
    message_user_card,
    user_card,
};

export function any_active() {
    return Object.values(user_card_popovers).some((instance) => instance.is_open());
}

export function hide_all_instances() {
    for (const key in user_card_popovers) {
        if (user_card_popovers[key].hide) {
            user_card_popovers[key].hide();
        }
    }
}

export function hide_all_user_card_popovers() {
    hide_all_instances();
}

export function clear_for_testing() {
    message_user_card.instance = undefined;
    user_card.instance = undefined;
    manage_menu.instance = undefined;
}

function elem_to_user_id($elem) {
    return Number.parseInt($elem.attr("data-user-id"), 10);
}

function clipboard_enable(arg) {
    // arg is a selector or element
    // We extract this function for testing purpose.
    return new ClipboardJS(arg);
}

// Functions related to user card popover.

export function toggle_user_card_popover(element, user) {
    show_user_card_popover(
        user,
        $(element),
        false,
        false,
        "compose_private_message",
        "user_card",
        "right",
    );
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
    const field_types = realm.custom_profile_field_types;
    const display_profile_fields = realm.custom_profile_fields
        .map((f) => user_profile.get_custom_profile_field_data(user, f, field_types))
        .filter((f) => f.display_in_profile_summary && f.value !== undefined && f.value !== null);

    const args = {
        invisible_mode,
        can_send_private_message:
            is_active &&
            !is_me &&
            realm.realm_private_message_policy !==
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
        user_mention_syntax: people.get_mention_syntax(user.full_name, user.user_id, !is_active),
        date_joined,
        spectator_view,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(user.user_id),
    };

    if (user.is_bot) {
        const bot_owner_id = user.bot_owner_id;
        if (is_system_bot) {
            args.is_system_bot = is_system_bot;
        } else if (bot_owner_id) {
            const bot_owner = people.get_bot_owner_user(user);
            args.bot_owner = bot_owner;
        }
    }

    return args;
}

function show_user_card_popover(
    user,
    $popover_element,
    is_sender_popover,
    has_message_context,
    private_msg_class,
    template_class,
    popover_placement,
    on_mount,
) {
    let popover_html;
    let args;
    if (user.is_inaccessible_user) {
        const sent_by_url = hash_util.by_sender_url(user.email);
        args = {
            user_id: user.user_id,
            sent_by_url,
        };
        popover_html = render_user_card_popover_for_unknown_user(args);
    } else {
        args = get_user_card_popover_data(
            user,
            has_message_context,
            is_sender_popover,
            private_msg_class,
        );
        popover_html = render_user_card_popover(args);
    }

    popover_menus.toggle_popover_menu(
        $popover_element[0],
        {
            placement: popover_placement,
            arrow: false,
            onCreate(instance) {
                instance.setContent(ui_util.parse_html(popover_html));
                user_card_popovers[template_class].instance = instance;

                const $popover = $(instance.popper);
                const $popover_title = $popover.find(".user-card-popover-title");

                $popover.addClass(get_popover_classname(template_class));
                $popover_title.append(
                    $(
                        render_user_card_popover_avatar({
                            // See the load_medium_avatar comment for important background.
                            user_avatar: people.small_avatar_url_for_person(user),
                            user_is_guest: user.is_guest,
                        }),
                    ),
                );
            },
            onHidden() {
                user_card_popovers[template_class].hide();
            },
            onMount(instance) {
                if (on_mount) {
                    on_mount(instance);
                }
                // Note: We pass the normal-size avatar in initial rendering, and
                // then query the server to replace it with the medium-size
                // avatar.  The purpose of this double-fetch approach is to take
                // advantage of the fact that the browser should already have the
                // low-resolution image cached and thus display a low-resolution
                // avatar rather than a blank area during the network delay for
                // fetching the medium-size one.
                load_medium_avatar(user, $(".popover-avatar"));
                init_email_clipboard();
                init_email_tooltip(user);

                const $popover = $(instance.popper);
                const $user_name_element = $popover.find(".user_full_name");
                const $bot_owner_element = $popover.find(".bot_owner");

                if (
                    $user_name_element.prop("clientWidth") < $user_name_element.prop("scrollWidth")
                ) {
                    $user_name_element.addClass("tippy-zulip-tooltip");
                }
                if (
                    args.bot_owner &&
                    $bot_owner_element.prop("clientWidth") < $bot_owner_element.prop("scrollWidth")
                ) {
                    $bot_owner_element.addClass("tippy-zulip-tooltip");
                }
            },
        },
        {
            show_as_overlay_on_mobile: true,
        },
    );
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
    const is_me = people.is_my_user_id(user.user_id);
    const is_muted = muted_users.is_user_muted(user.user_id);
    const is_system_bot = user.is_system_bot;
    const muting_allowed = !is_me;

    const args = {
        can_mute: muting_allowed && !is_muted,
        can_manage_user: current_user.is_admin && !is_me && !is_system_bot,
        can_unmute: muting_allowed && is_muted,
        is_active: people.is_active_user_for_popover(user.user_id),
        is_bot: user.is_bot,
        user_id: user.user_id,
    };

    popover_menus.toggle_popover_menu(element, {
        placement: "bottom",
        onCreate(instance) {
            manage_menu.instance = instance;
            const $popover = $(instance.popper);
            $popover.addClass("manage-menu-popover-root");
            instance.setContent(ui_util.parse_html(render_user_card_popover_manage_menu(args)));
        },
        onHidden() {
            manage_menu.hide();
        },
    });
}

export function get_user_card_popover_manage_menu_items() {
    if (!manage_menu.is_open()) {
        blueslip.error("Trying to get menu items when manage menu popover is closed.");
        return undefined;
    }

    const $popover = $(manage_menu.instance.popper);
    if (!$popover) {
        blueslip.error("Cannot find popover data for manage menu.");
        return undefined;
    }

    return $(".user-card-popover-manage-menu li:not(.divider):visible a", $popover);
}

// Functions related to message user card popover.

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function toggle_user_card_popover_for_message(element, user, message, on_mount) {
    const $elt = $(element);
    if (!message_user_card.is_open()) {
        if (user === undefined) {
            // This is never supposed to happen, not even for deactivated
            // users, so we'll need to debug this error if it occurs.
            blueslip.error("Bad sender in message", {
                message_id: message.id,
                sender_id: message.sender_id,
            });
            return;
        }

        const is_sender_popover = message.sender_id === user.user_id;
        show_user_card_popover(
            user,
            $elt,
            is_sender_popover,
            true,
            "respond_personal_button",
            "message_user_card",
            "right",
            undefined,
            on_mount,
        );
    }
}

// This function serves as the entry point for toggling
// the user card popover via keyboard shortcut.
export function toggle_sender_info() {
    if (message_user_card.is_open()) {
        // We need to call the hide method here because
        // the event wasn't triggered by the mouse.
        // The Tippy unTrigger event wasn't called,
        // so we have to manually hide the popover.
        message_user_card.hide();
        return;
    }
    const $message = $(".selected_message");
    let $sender = $message.find(".message-avatar");
    if ($sender.length === 0) {
        // Messages without an avatar have an invisible message_sender
        // element that's roughly in the right place.
        $sender = $message.find(".message_sender");
    }

    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(rows.id($message));
    const user = people.get_by_user_id(message.sender_id);
    toggle_user_card_popover_for_message($sender[0], user, message, () => {
        if (!page_params.is_spectator) {
            focus_user_card_popover_item();
        }
    });
}

function focus_user_card_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_user_card_popover_for_message_items();

    if ($(".user-card-popover-manage-menu-btn").is(":visible")) {
        popover_menus.focus_first_popover_item($items, 1);
    } else {
        popover_menus.focus_first_popover_item($items);
    }
}

function get_user_card_popover_for_message_items() {
    if (!message_user_card.is_open()) {
        blueslip.error("Trying to get menu items when message user card popover is closed.");
        return undefined;
    }

    const $popover = $(message_user_card.instance.popper);
    if (!$popover) {
        blueslip.error("Cannot find popover data for message user card menu.");
        return undefined;
    }

    return $("li:not(.divider):visible a", $popover);
}

// Functions related to the user card popover in the user sidebar.

function toggle_sidebar_user_card_popover($target) {
    const user_id = elem_to_user_id($target.find("a"));
    const user = people.get_by_user_id(user_id);

    // Hiding popovers may mutate current_user_sidebar_user_id.
    const previous_user_sidebar_id = current_user_sidebar_user_id;

    // Hide popovers
    hide_all();

    if (previous_user_sidebar_id === user_id) {
        // If the popover is already shown, clicking again should toggle it.
        return;
    }

    show_user_card_popover(
        user,
        $target,
        false,
        false,
        "compose_private_message",
        "user_sidebar",
        "left",
        undefined,
        (instance) => {
            /* See comment in get_props_for_popover_centering for explanation of this. */
            $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");
        },
    );

    current_user_sidebar_user_id = user.user_id;
}

function register_click_handlers() {
    $("#main_div").on("click", ".sender_name, .inline_profile_picture", function (e) {
        const $row = $(this).closest(".message_row");
        e.stopPropagation();
        assert(message_lists.current !== undefined);
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
        assert(message_lists.current !== undefined);
        const message = message_lists.current.get(rows.id($row));
        let user;
        if (id_string) {
            const user_id = Number.parseInt(id_string, 10);
            user = people.get_by_user_id(user_id);
        } else {
            user = people.get_by_email(email);
            if (user === undefined) {
                // There can be a case when user is undefined if
                // the user is an inaccessible user as we do not
                // create the fake user objects for it because
                // we do not have user ID. It is fine to not
                // open popover for this case as such cases
                // without user ID are rare and old.
                return;
            }
        }
        toggle_user_card_popover_for_message(this, user, message);
    });

    $("body").on("click", ".user-card-popover-actions .narrow_to_private_messages", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        narrow.by("dm", email, {trigger: "user sidebar popover"});
        hide_all();
        if (overlays.any_active()) {
            overlays.close_active();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".user-card-popover-actions .narrow_to_messages_sent", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        narrow.by("sender", email, {trigger: "user sidebar popover"});
        hide_all();
        if (overlays.any_active()) {
            overlays.close_active();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".user-card-popover-actions .user-card-clear-status-button", (e) => {
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

    $("body").on("click", ".sidebar-popover-reactivate-user", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        hide_all();
        e.stopPropagation();
        e.preventDefault();
        function handle_confirm() {
            const url = "/json/users/" + encodeURIComponent(user_id) + "/reactivate";
            channel.post({
                url,
                success() {
                    dialog_widget.close();
                },
                error(xhr) {
                    ui_report.error($t_html({defaultMessage: "Failed"}), xhr, $("#dialog_error"));
                    dialog_widget.hide_dialog_spinner();
                },
            });
        }
        user_deactivation_ui.confirm_reactivation(user_id, handle_confirm, true);
    });

    $("body").on("click", ".user-card-popover-actions .view_full_user_profile", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        browser_history.go_to_location(`user/${user_id}`);
        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".user-card-popover-root .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_actions.start({
                message_type: "stream",
                trigger: "sidebar user actions",
                keep_composebox_empty: true,
            });
        }
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        user_sidebar.hide();
        sidebar_ui.hide_userlist_sidebar();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".message-user-card-popover-root .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_reply.respond_to_message({
                trigger: "user sidebar popover",
                keep_composebox_empty: true,
            });
        }
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const is_active = people.is_active_user_for_popover(user_id);
        const mention = people.get_mention_syntax(name, user_id, !is_active);
        compose_ui.insert_syntax_and_focus(mention);
        message_user_card.hide();
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
    $(".buddy-list-section").on(
        "click",
        ".user_sidebar_entry_me .status-emoji",
        open_user_status_modal,
    );

    $(".buddy-list-section").on("click", ".user-list-sidebar-menu-icon", (e) => {
        e.stopPropagation();
        const $target = $(e.currentTarget).closest("li");

        toggle_sidebar_user_card_popover($target);
    });

    $("body").on("click", ".sidebar-popover-mute-user", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        hide_all_user_card_popovers();
        e.stopPropagation();
        e.preventDefault();
        confirm_mute_user(user_id);
    });

    $("body").on("click", ".sidebar-popover-unmute-user", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        hide_all_user_card_popovers();
        muted_users.unmute_user(user_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".respond_personal_button, .compose_private_message", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        compose_actions.start({
            message_type: "private",
            trigger: "popover send private",
            private_message_recipient: email,
        });
        hide_all();
        if (overlays.any_active()) {
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
    new ClipboardJS(".copy-custom-field-url", {
        text(trigger) {
            return $(trigger)
                .closest(".custom-user-url-field")
                .find(".custom-profile-fields-link")
                .attr("href");
        },
    }).on("success", (e) => {
        show_copied_confirmation(e.trigger);
    });
}

export function initialize() {
    register_click_handlers();
    clipboard_enable(".copy_mention_syntax");
}
