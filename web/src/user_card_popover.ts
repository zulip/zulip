import ClipboardJS from "clipboard";
import {parseISO} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_confirm_mute_user from "../templates/confirm_dialog/confirm_mute_user.hbs";
import render_user_card_popover from "../templates/popovers/user_card/user_card_popover.hbs";
import render_user_card_popover_for_unknown_user from "../templates/popovers/user_card/user_card_popover_for_unknown_user.hbs";

import * as blueslip from "./blueslip.ts";
import * as browser_history from "./browser_history.ts";
import * as buddy_data from "./buddy_data.ts";
import * as channel from "./channel.ts";
import * as compose_actions from "./compose_actions.ts";
import * as compose_reply from "./compose_reply.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as confirm_dialog from "./confirm_dialog.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {is_overlay_hash} from "./hash_parser.ts";
import * as hash_util from "./hash_util.ts";
import {$t, $t_html} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import {user_can_send_direct_message} from "./message_util.ts";
import * as message_view from "./message_view.ts";
import * as mouse_drag from "./mouse_drag.ts";
import * as muted_users from "./muted_users.ts";
import * as overlays from "./overlays.ts";
import {page_params} from "./page_params.ts";
import type {User} from "./people.ts";
import * as people from "./people.ts";
import * as popover_menus from "./popover_menus.ts";
import * as popovers from "./popovers.ts";
import {hide_all} from "./popovers.ts";
import * as presence from "./presence.ts";
import * as rows from "./rows.ts";
import * as settings_panel_menu from "./settings_panel_menu.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import {current_user, realm} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import * as ui_util from "./ui_util.ts";
import * as user_deactivation_ui from "./user_deactivation_ui.ts";
import type {CustomProfileFieldData} from "./user_profile.ts";
import * as user_profile from "./user_profile.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import * as user_status_ui from "./user_status_ui.ts";
import {the} from "./util.ts";

let current_user_sidebar_user_id: number | undefined;

export function confirm_mute_user(user_id: number): void {
    function on_click(): void {
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
    instance: tippy.Instance | undefined;

    constructor() {
        this.instance = undefined;
    }

    is_open(): boolean {
        return Boolean(this.instance);
    }

    hide(): void {
        if (this.instance) {
            this.instance.destroy();
            this.instance = undefined;
        }
    }

    handle_keyboard(key: string): void {
        if (!this.instance) {
            blueslip.error("Trying to get the items when popover is closed.");
            return;
        }

        const $popover = $(this.instance.popper);

        const $items = $("[tabindex='0']", $popover);

        popover_items_handle_keyboard_with_overrides(key, $items);
    }
}

export const user_sidebar = new PopoverMenu();
export const message_user_card = new PopoverMenu();
export const user_card = new PopoverMenu();

function popover_items_handle_keyboard_with_overrides(key: string, $items: JQuery): void {
    /* Variant of popover_items_handle_keyboard for focusing on the
       user card popover menu options first, instead of other tabbable
       buttons and links which can be distracting. */

    const index = $items.index($items.filter(":focus"));

    if (index === -1) {
        const $menu_options = $items.filter(".link-item .popover-menu-link");
        [...$menu_options].find((option) => option.getClientRects().length)?.focus();
        return;
    }

    /* Otherwise, use the base implementation */
    popover_menus.popover_items_handle_keyboard(key, $items);
}

function get_popover_classname(
    popover: "user_sidebar" | "message_user_card" | "user_card",
): string {
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
    user_sidebar,
    message_user_card,
    user_card,
};

export function any_active(): boolean {
    return Object.values(user_card_popovers).some((instance) => instance.is_open());
}

export function hide_all_instances(): void {
    for (const popover of Object.values(user_card_popovers)) {
        popover.hide();
    }
}

export function hide_all_user_card_popovers(): void {
    hide_all_instances();
}

export function clear_for_testing(): void {
    message_user_card.instance = undefined;
    user_card.instance = undefined;
}

function elem_to_user_id($elem: JQuery): number {
    return Number.parseInt($elem.attr("data-user-id")!, 10);
}

function clipboard_enable(arg: HTMLElement | string): ClipboardJS {
    // arg is a selector or element
    // We extract this function for testing purpose.
    return new ClipboardJS(arg);
}

// Functions related to user card popover.

export function toggle_user_card_popover(element: HTMLElement, user: User): void {
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

function toggle_user_card_popover_for_bot_owner(element: HTMLElement, user: User): void {
    show_user_card_popover(
        user,
        $(element),
        false,
        false,
        "compose_private_message",
        "user_card",
        "right",
        true,
    );
}

type UserCardPopoverData = {
    invisible_mode: boolean;
    can_send_private_message: boolean;
    display_profile_fields: CustomProfileFieldData[];
    has_message_context: boolean;
    is_active: boolean;
    is_bot: boolean;
    is_me: boolean;
    is_sender_popover: boolean;
    pm_with_url: string;
    user_circle_class: string;
    private_message_class: string;
    sent_by_url: string;
    user_email: string | null;
    user_full_name: string;
    user_id: number;
    user_last_seen_time_status: string;
    user_time: string | undefined;
    user_type: string | undefined;
    status_content_available: boolean;
    status_text: string | undefined;
    status_emoji_info: user_status.UserStatusEmojiInfo | undefined;
    show_placeholder_for_status_text: false | user_status.UserStatusEmojiInfo | undefined;
    user_mention_syntax: string;
    date_joined: string | undefined;
    spectator_view: boolean;
    should_add_guest_user_indicator: boolean;
    user_avatar: string;
    user_is_guest: boolean;
    show_manage_section: boolean;
    can_mute: boolean;
    can_unmute: boolean;
    can_manage_user: boolean;
    is_system_bot?: boolean;
    bot_owner?: User;
};

export let fetch_presence_for_popover = (user_id: number): void => {
    if (page_params.is_spectator) {
        return;
    }

    if (!people.is_active_user_for_popover(user_id) || people.get_by_user_id(user_id).is_bot) {
        return;
    }

    const url = `json/users/${user_id}/presence`;
    const selector_to_update = `#user_card_popover .popover-menu-list[data-user-id="${CSS.escape(user_id.toString())}"] .user-last-seen-time`;
    channel.get({
        url,
        success(data: unknown) {
            const parsed_data = presence.user_last_seen_response_schema.safeParse(data);

            if (!parsed_data.success) {
                blueslip.error("Failed to parse presence API response");
                return;
            }

            const response = parsed_data.data;

            if (response.result === "success" && response.presence) {
                const {aggregated} = response.presence;
                presence.presence_info.set(user_id, {
                    status: aggregated.status,
                    last_active: aggregated.timestamp,
                });

                // Update the user's last seen time in the user card
                // popover once we have their presence information, if
                // we still have that user card still open.
                $(selector_to_update).text(buddy_data.user_last_seen_time_status(user_id));
            }
        },
        error() {
            // Fallback logic for users who haven't generated any presence data.
            // A non-bot active user account might have no presence data either
            // because they have always been in "invisible mode" or because the
            // account was imported from another chat system.
            //
            // Store the fact that this user hasn't been online since
            // account creation, to avoid uselessly asking the server
            // again in this session.
            const user = people.get_by_user_id(user_id);
            presence.presence_info.set(user_id, {
                status: "offline",
                last_active: new Date(user.date_joined).getTime() / 1000,
            });
            $(selector_to_update).text(buddy_data.user_last_seen_time_status(user_id));
        },
    });
};

export function rewire_fetch_presence_for_popover(value: (user_id: number) => string): void {
    fetch_presence_for_popover = value;
}

function get_user_card_popover_data(
    user: User,
    has_message_context: boolean,
    is_sender_popover: boolean,
    private_msg_class: string,
): UserCardPopoverData {
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
    const show_manage_section = !spectator_view && !is_me;
    const is_muted = muted_users.is_user_muted(user.user_id);
    const muting_allowed = !is_me;
    const can_mute = muting_allowed && !is_muted;
    const can_unmute = muting_allowed && is_muted;
    const can_manage_user = current_user.is_admin && !is_me && !is_system_bot;

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
        .flatMap((f) => user_profile.get_custom_profile_field_data(user, f, field_types) ?? [])
        .filter((f) => f.display_in_profile_summary && f.value !== undefined && f.value !== null);

    const user_id_string = user.user_id.toString();
    const can_send_private_message =
        user_can_send_direct_message(user_id_string) && is_active && !is_me;

    const user_last_seen_time_status =
        buddy_data.user_last_seen_time_status(user.user_id, fetch_presence_for_popover) ||
        $t({defaultMessage: "Loading…"});

    const args: UserCardPopoverData = {
        invisible_mode,
        can_send_private_message,
        display_profile_fields,
        has_message_context,
        is_active,
        is_bot: user.is_bot,
        is_me,
        is_sender_popover,
        pm_with_url: hash_util.pm_with_url(user.user_id.toString()),
        user_circle_class: buddy_data.get_user_circle_class(user.user_id),
        private_message_class: private_msg_class,
        sent_by_url: hash_util.by_sender_url(user.email),
        user_email: user.delivery_email,
        user_full_name: user.full_name,
        user_id: user.user_id,
        user_last_seen_time_status,
        user_time: people.get_user_time(user.user_id),
        user_type: people.get_user_type(user.user_id),
        status_content_available: Boolean(status_text ?? status_emoji_info),
        status_text,
        status_emoji_info,
        show_placeholder_for_status_text: !status_text && status_emoji_info,
        user_mention_syntax: people.get_mention_syntax(user.full_name, user.user_id, !is_active),
        date_joined,
        spectator_view,
        should_add_guest_user_indicator: people.should_add_guest_user_indicator(user.user_id),
        user_avatar: people.small_avatar_url_for_person(user),
        user_is_guest: user.is_guest,
        show_manage_section,
        can_mute,
        can_unmute,
        can_manage_user,
    };

    if (user.is_bot) {
        const bot_owner_id = user.bot_owner_id;
        if (is_system_bot) {
            args.is_system_bot = is_system_bot;
        } else if (bot_owner_id) {
            const bot_owner = people.get_user_by_id_assert_valid(bot_owner_id);
            args.bot_owner = bot_owner;
        }
    }

    return args;
}

function show_user_card_popover(
    user: User,
    $popover_element: JQuery,
    is_sender_popover: boolean,
    has_message_context: boolean,
    private_msg_class: string,
    template_class: "user_sidebar" | "message_user_card" | "user_card",
    popover_placement: tippy.Placement,
    show_as_overlay = false,
    on_mount?: (instance: tippy.Instance) => void,
): void {
    let popover_html;
    let args;
    if (user.is_inaccessible_user) {
        const sent_by_url = hash_util.by_sender_url(user.email);
        const user_avatar = people.small_avatar_url_for_person(user);
        args = {
            user_id: user.user_id,
            sent_by_url,
            user_avatar,
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
        the($popover_element),
        {
            theme: "popover-menu",
            placement: popover_placement,
            onCreate(instance) {
                instance.setContent(ui_util.parse_html(popover_html));
                user_card_popovers[template_class].instance = instance;

                const $popover = $(instance.popper);

                $popover.addClass(get_popover_classname(template_class));
            },
            onHidden() {
                user_card_popovers[template_class].hide();
            },
            onMount(instance) {
                if (on_mount) {
                    on_mount(instance);
                }
                const $popover = $(instance.popper);
                // Note: We pass the normal-size avatar in initial rendering, and
                // then query the server to replace it with the medium-size
                // avatar.  The purpose of this double-fetch approach is to take
                // advantage of the fact that the browser should already have the
                // low-resolution image cached and thus display a low-resolution
                // avatar rather than a blank area during the network delay for
                // fetching the medium-size one.
                load_medium_avatar(user, $popover.find(".popover-menu-user-avatar"));
                init_email_clipboard();
                init_email_tooltip(user);
            },
        },
        {
            show_as_overlay_on_mobile: true,
            show_as_overlay_always: show_as_overlay,
        },
    );
}

function init_email_clipboard(): void {
    /*
        This shows (and enables) the copy-text icon for folks
        who have names that would overflow past the right
        edge of our user mention popup.
    */
    $(".user_popover_email").each(function () {
        if (this.clientWidth < this.scrollWidth) {
            const $email_el = $(this).parent();
            const $copy_email_icon = $email_el.find("#popover-menu-copy-email");

            /*
                For deactivated users, the copy-email icon will
                not even be present in the HTML, so we don't do
                anything.  We don't reveal emails for deactivated
                users.
            */
            if ($copy_email_icon[0]) {
                $copy_email_icon.removeClass("hide_copy_icon");
                const copy_email_clipboard = clipboard_enable($copy_email_icon[0]);
                copy_email_clipboard.on("success", (e) => {
                    show_copied_confirmation(e.trigger, {
                        show_check_icon: true,
                    });
                });
            }
        }
    });
}

function init_email_tooltip(user: User): void {
    /*
        This displays the email tooltip for folks
        who have names that would overflow past the right
        edge of our user mention popup.
    */

    $(".user_popover_email").each(function () {
        if (this.clientWidth < this.scrollWidth) {
            tippy.default(this, {
                content: people.get_visible_email(user),
                appendTo: () => document.body,
            });
        }
    });
}

function load_medium_avatar(user: User, $elt: JQuery): void {
    const user_avatar_url = people.medium_avatar_url_for_person(user);
    const sender_avatar_medium = new Image();

    sender_avatar_medium.src = user_avatar_url;
    $(sender_avatar_medium).on("load", function () {
        $elt.attr("src", $(this).attr("src")!);
    });
}

// Functions related to message user card popover.

// element is the target element to pop off of.
// user is the user whose profile to show.
// sender_id is the user id of the sender for the message we are
// showing the popover from.
export function toggle_user_card_popover_for_message(
    element: HTMLElement,
    user: User,
    sender_id: number,
    has_message_context: boolean,
    on_mount?: (instance: tippy.Instance) => void,
): void {
    const $elt = $(element);

    const is_sender_popover = sender_id === user.user_id;
    show_user_card_popover(
        user,
        $elt,
        is_sender_popover,
        has_message_context,
        "respond_personal_button",
        "message_user_card",
        "right",
        false,
        on_mount,
    );
}

export function unsaved_message_user_mention_event_handler(
    this: HTMLElement,
    e: JQuery.ClickEvent,
): void {
    if (document.getSelection()?.type === "Range") {
        return;
    }

    e.stopPropagation();

    const id_string = $(this).attr("data-user-id")!;
    // Do not open popover for @all mention
    if (id_string === "*") {
        return;
    }

    const user_id = Number.parseInt(id_string, 10);
    const user = people.get_by_user_id(user_id);

    toggle_user_card_popover_for_message(this, user, current_user.user_id, false);
}

// This function serves as the entry point for toggling
// the user card popover via keyboard shortcut.
export function toggle_sender_info(): void {
    if (message_user_card.is_open()) {
        // We need to call the hide method here because
        // the event wasn't triggered by the mouse.
        // The Tippy unTrigger event wasn't called,
        // so we have to manually hide the popover.
        message_user_card.hide();
        return;
    }

    // The "View user card" tooltip shown when hovering the avatar can
    // block this from opening properly, so close it first.
    //
    // This isn't necessary for the click handler, because the click
    // naturally closes the Tippy tooltip.
    popovers.hide_all();

    const $message = $(".selected_message");
    let $sender = $message.find(".message-avatar");
    if ($sender.length === 0) {
        // Messages without an avatar have an invisible message_sender
        // element that's roughly in the right place.
        $sender = $message.find(".message_sender");
    }

    assert(message_lists.current !== undefined);
    const message = message_lists.current.get(rows.id($message));
    assert(message !== undefined);
    const user = people.get_by_user_id(message.sender_id);
    toggle_user_card_popover_for_message(the($sender), user, message.sender_id, true, () => {
        if (!page_params.is_spectator) {
            focus_user_card_popover_item();
        }
    });
}

function focus_user_card_popover_item(): void {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const $items = get_user_card_popover_for_message_items();
    [...($items ?? [])].find((item) => item.getClientRects().length)?.focus();
}

function get_user_card_popover_for_message_items(): JQuery | undefined {
    if (!message_user_card.is_open()) {
        blueslip.error("Trying to get menu items when message user card popover is closed.");
        return undefined;
    }

    if (message_user_card.instance === undefined) {
        blueslip.error("Cannot find popover data for message user card menu.");
        return undefined;
    }
    const $popover = $(message_user_card.instance.popper);

    // Return only the popover menu options that are visible, and not the
    // copy buttons or the link items in the custom profile fields.
    return $(".link-item .popover-menu-link", $popover);
}

// Functions related to the user card popover in the user sidebar.

function toggle_sidebar_user_card_popover($target: JQuery): void {
    const user_id = elem_to_user_id($target);
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
        false,
        (instance) => {
            /* See comment in get_props_for_popover_centering for explanation of this. */
            $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");
        },
    );

    current_user_sidebar_user_id = user.user_id;
}

function register_click_handlers(): void {
    $("#main_div").on(
        "click",
        ".sender_name, .inline-profile-picture-wrapper",
        function (this: HTMLElement, e) {
            e.stopPropagation();
            if (mouse_drag.is_drag(e)) {
                return;
            }
            const $row = $(this).closest(".message_row");
            assert(message_lists.current !== undefined);
            const message = message_lists.current.get(rows.id($row));
            assert(message !== undefined);
            const user = people.get_by_user_id(message.sender_id);
            toggle_user_card_popover_for_message(this, user, message.sender_id, true);
        },
    );

    $("#main_div").on("click", ".user-mention", function (this: HTMLElement, e) {
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
        assert(message !== undefined);
        let user;
        if (id_string) {
            const user_id = Number.parseInt(id_string, 10);
            user = people.get_by_user_id(user_id);
        } else {
            user = email === undefined ? undefined : people.get_by_email(email);
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
        toggle_user_card_popover_for_message(this, user, message.sender_id, true);
    });

    // Note: Message feeds and drafts have their own direct event listeners
    // that run before this one and call stopPropagation.
    $("body").on("click", ".messagebox .user-mention", unsaved_message_user_mention_event_handler);

    $("body").on("click", ".user-card-popover-actions .narrow_to_private_messages", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        message_view.show(
            [
                {
                    operator: "dm",
                    operand: email,
                },
            ],
            {trigger: "user sidebar popover"},
        );
        hide_all();
        if (overlays.any_active()) {
            overlays.close_active();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".user-card-popover-actions .narrow_to_messages_sent", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        message_view.show(
            [
                {
                    operator: "sender",
                    operand: email,
                },
            ],
            {trigger: "user sidebar popover"},
        );
        hide_all();
        if (overlays.any_active()) {
            overlays.close_active();
        }
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".user-card-popover-actions .user-card-clear-status-button", (e) => {
        e.preventDefault();
        user_status.server_update_status({
            status_text: "",
            emoji_name: "",
            emoji_code: "",
            success() {
                hide_all_user_card_popovers();
            },
        });
    });

    $("body").on("click", ".sidebar-popover-reactivate-user", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        hide_all();
        e.stopPropagation();
        e.preventDefault();
        function handle_confirm(): void {
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

    $("body").on("click", ".user-card-popover-actions .view_full_user_profile", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        const current_hash = window.location.hash;
        // If any overlay is already open, we want the user profile to behave
        // as a modal rather than an overlay.
        if (is_overlay_hash(current_hash)) {
            const user = people.get_by_user_id(user_id);
            user_profile.show_user_profile(user);
        } else {
            browser_history.go_to_location(`user/${user_id}`);
        }
        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".user-card-popover-root .mention_user", function (e) {
        if (!compose_state.composing()) {
            compose_actions.start({
                message_type: "stream",
                trigger: "sidebar user actions",
                keep_composebox_empty: true,
            });
        }
        const user_id = elem_to_user_id($(this).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        user_sidebar.hide();
        sidebar_ui.hide_userlist_sidebar();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".message-user-card-popover-root .mention_user", function (e) {
        if (!compose_state.composing()) {
            compose_reply.respond_to_message({
                trigger: "user sidebar popover",
                keep_composebox_empty: true,
            });
        }
        const user_id = elem_to_user_id($(this).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const is_active = people.is_active_user_for_popover(user_id);
        const mention = people.get_mention_syntax(name, user_id, !is_active);
        compose_ui.insert_syntax_and_focus(mention);
        message_user_card.hide();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on(
        "click",
        ".view_user_profile, .person_picker .pill[data-user-id]",
        function (this: HTMLElement, e) {
            const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id")!, 10);
            const user = people.get_by_user_id(user_id);
            if ($(this).closest(".user-card-popover-bot-owner-field").length > 0) {
                hide_all_user_card_popovers();
                toggle_user_card_popover_for_bot_owner(this, user);
            } else {
                toggle_user_card_popover(this, user);
            }
            e.stopPropagation();
            e.preventDefault();
        },
    );

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

    function open_user_status_modal(e: JQuery.ClickEvent): void {
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

    $(".buddy-list-section").on("click", ".user-profile-picture", (e) => {
        e.stopPropagation();
        const $target = $(e.currentTarget).closest("li");

        toggle_sidebar_user_card_popover($target);
    });

    $("body").on("click", ".sidebar-popover-mute-user", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        hide_all_user_card_popovers();
        e.stopPropagation();
        e.preventDefault();
        confirm_mute_user(user_id);
    });

    $("body").on("click", ".sidebar-popover-unmute-user", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        hide_all_user_card_popovers();
        muted_users.unmute_user(user_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".respond_personal_button, .compose_private_message", function (e) {
        const user_id = elem_to_user_id($(this).parents("ul"));
        compose_actions.start({
            message_type: "private",
            trigger: "popover send private",
            private_message_recipient_ids: [user_id],
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

    $("body").on("click", ".sidebar-popover-manage-user", function () {
        hide_all();
        const user_id = elem_to_user_id($(this).parents("ul"));
        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user, "manage-profile-tab");
    });

    $("body").on("click", ".edit-your-profile", () => {
        hide_all();
        window.location.hash = "#settings/profile";
        settings_panel_menu.mobile_activate_section();
    });

    new ClipboardJS(".copy-custom-profile-field-link", {
        text(trigger): string {
            return $(trigger).parent().find(".custom-profile-field-link").attr("href")!;
        },
    }).on("success", (e) => {
        show_copied_confirmation(e.trigger, {
            show_check_icon: true,
        });
    });
}

export function initialize(): void {
    register_click_handlers();
    clipboard_enable(".copy_mention_syntax");
}
