"use strict";

const ClipboardJS = require("clipboard");
const {parseISO, formatISO, add, set} = require("date-fns");
const ConfirmDatePlugin = require("flatpickr/dist/plugins/confirmDate/confirmDate");

const render_actions_popover_content = require("../templates/actions_popover_content.hbs");
const render_confirm_user_deactivation_modal = require("../templates/confirm_user_deactivation_modal.hbs");
const render_mobile_message_buttons_popover = require("../templates/mobile_message_buttons_popover.hbs");
const render_mobile_message_buttons_popover_content = require("../templates/mobile_message_buttons_popover_content.hbs");
const render_no_arrow_popover = require("../templates/no_arrow_popover.hbs");
const render_playground_links_popover_content = require("../templates/playground_links_popover_content.hbs");
const render_remind_me_popover_content = require("../templates/remind_me_popover_content.hbs");
const render_user_group_info_popover = require("../templates/user_group_info_popover.hbs");
const render_user_group_info_popover_content = require("../templates/user_group_info_popover_content.hbs");
const render_user_info_popover_content = require("../templates/user_info_popover_content.hbs");
const render_user_info_popover_title = require("../templates/user_info_popover_title.hbs");
const render_user_profile_modal = require("../templates/user_profile_modal.hbs");

const feature_flags = require("./feature_flags");
const message_edit_history = require("./message_edit_history");
const people = require("./people");
const settings_config = require("./settings_config");
const settings_data = require("./settings_data");
const user_status = require("./user_status");
const user_status_ui = require("./user_status_ui");
const util = require("./util");

let current_actions_popover_elem;
let current_flatpickr_instance;
let current_message_info_popover_elem;
let current_mobile_message_buttons_popover_elem;
let current_user_info_popover_elem;
let current_playground_links_popover_elem;
let userlist_placement = "right";

let list_of_popovers = [];

function elem_to_user_id(elem) {
    return Number.parseInt(elem.attr("data-user-id"), 10);
}

// this utilizes the proxy pattern to intercept all calls to $.fn.popover
// and push the $.fn.data($o, "popover") results to an array.
// this is needed so that when we try to unload popovers, we can kill all dead
// ones that no longer have valid parents in the DOM.
(function (popover) {
    $.fn.popover = function (...args) {
        // apply the jQuery object as `this`, and popover function arguments.
        popover.apply(this, args);

        // if there is a valid "popover" key in the jQuery data object then
        // push it to the array.
        if (this.data("popover")) {
            list_of_popovers.push(this.data("popover"));
        }
    };

    // add back all shallow properties of $.fn.popover to the new proxied version.
    Object.assign($.fn.popover, popover);
})($.fn.popover);

function copy_email_handler(e) {
    const email_el = $(e.trigger.parentElement);
    const copy_icon = email_el.find("i");

    // only change the parent element's text back to email
    // and not overwrite the tooltip.
    const email_textnode = email_el[0].childNodes[2];

    email_el.addClass("email_copied");
    email_textnode.nodeValue = i18n.t("Email copied");

    setTimeout(() => {
        email_el.removeClass("email_copied");
        email_textnode.nodeValue = copy_icon.attr("data-clipboard-text");
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
            const email_el = $(this);
            const copy_email_icon = email_el.find("i");

            /*
                For deactivated users, the copy-email icon will
                not even be present in the HTML, so we don't do
                anything.  We don't reveal emails for deactivated
                users.
            */
            if (copy_email_icon[0]) {
                copy_email_icon.removeClass("hide_copy_icon");
                const copy_email_clipboard = new ClipboardJS(copy_email_icon[0]);
                copy_email_clipboard.on("success", copy_email_handler);
            }
        }
    });
}

function load_medium_avatar(user, elt) {
    const avatar_path = "avatar/" + user.user_id + "/medium?v=" + user.avatar_version;
    const user_avatar_url = new URL(avatar_path, window.location.href);
    const sender_avatar_medium = new Image();

    sender_avatar_medium.src = user_avatar_url;
    $(sender_avatar_medium).on("load", function () {
        elt.css("background-image", "url(" + $(this).attr("src") + ")");
    });
}

function calculate_info_popover_placement(size, elt) {
    const ypos = elt.offset().top;

    if (!(ypos + size / 2 < message_viewport.height() && ypos > size / 2)) {
        if (ypos + size < message_viewport.height()) {
            return "bottom";
        } else if (ypos > size) {
            return "top";
        }
    }

    return undefined;
}

function get_custom_profile_field_data(user, field, field_types, dateFormat) {
    const field_value = people.get_custom_profile_data(user.user_id, field.id);
    const field_type = field.type;
    const profile_field = {};

    if (!field_value) {
        return profile_field;
    }
    if (!field_value.value) {
        return profile_field;
    }
    profile_field.name = field.name;
    profile_field.is_user_field = false;
    profile_field.is_link = field_type === field_types.URL.id;
    profile_field.is_external_account = field_type === field_types.EXTERNAL_ACCOUNT.id;
    profile_field.type = field_type;

    switch (field_type) {
        case field_types.DATE.id:
            profile_field.value = dateFormat.format(parseISO(field_value.value));
            break;
        case field_types.USER.id:
            profile_field.id = field.id;
            profile_field.is_user_field = true;
            profile_field.value = field_value.value;
            break;
        case field_types.CHOICE.id: {
            const field_choice_dict = JSON.parse(field.field_data);
            profile_field.value = field_choice_dict[field_value.value].text;
            break;
        }
        case field_types.SHORT_TEXT.id:
        case field_types.LONG_TEXT.id:
            profile_field.value = field_value.value;
            profile_field.rendered_value = field_value.rendered_value;
            break;
        case field_types.EXTERNAL_ACCOUNT.id:
            profile_field.value = field_value.value;
            profile_field.field_data = JSON.parse(field.field_data);
            profile_field.link = settings_profile_fields.get_external_account_link(profile_field);
            break;
        default:
            profile_field.value = field_value.value;
    }
    return profile_field;
}

function render_user_info_popover(
    user,
    popover_element,
    is_sender_popover,
    has_message_context,
    private_msg_class,
    template_class,
    popover_placement,
) {
    const is_me = people.is_my_user_id(user.user_id);

    let can_set_away = false;
    let can_revoke_away = false;

    if (is_me) {
        if (user_status.is_away(user.user_id)) {
            can_revoke_away = true;
        } else {
            can_set_away = true;
        }
    }

    const args = {
        can_revoke_away,
        can_set_away,
        has_message_context,
        is_active: people.is_active_user_for_popover(user.user_id),
        is_user_admin: page_params.is_admin,
        is_user_owner: page_params.is_owner,
        is_owner: user.is_owner,
        is_admin: user.is_admin,
        is_bot: user.is_bot,
        is_me,
        is_sender_popover,
        pm_with_uri: hash_util.pm_with_uri(user.email),
        user_circle_class: buddy_data.get_user_circle_class(user.user_id),
        private_message_class: private_msg_class,
        sent_by_uri: hash_util.by_sender_uri(user.email),
        show_email: settings_data.show_email(),
        show_user_profile: !(user.is_bot || page_params.custom_profile_fields.length === 0),
        user_email: people.get_visible_email(user),
        user_full_name: user.full_name,
        user_id: user.user_id,
        user_last_seen_time_status: buddy_data.user_last_seen_time_status(user.user_id),
        user_time: people.get_user_time(user.user_id),
        user_type: people.get_user_type(user.user_id),
        status_text: user_status.get_status_text(user.user_id),
        user_mention_syntax: people.get_mention_syntax(user.full_name, user.user_id),
    };

    if (user.is_bot) {
        const is_cross_realm_bot = user.is_cross_realm_bot;
        const bot_owner_id = user.bot_owner_id;
        if (is_cross_realm_bot) {
            args.is_cross_realm_bot = is_cross_realm_bot;
        } else if (bot_owner_id) {
            const bot_owner = people.get_by_user_id(bot_owner_id);
            args.bot_owner = bot_owner;
        }
    }

    popover_element.popover({
        content: render_user_info_popover_content(args),
        // TODO: Determine whether `fixed` should be applied
        // unconditionally.  Right now, we only do it for the user
        // sidebar version of the popover.
        fixed: template_class === "user_popover",
        placement: popover_placement,
        template: render_no_arrow_popover({class: template_class}),
        title: render_user_info_popover_title({
            user_avatar: "avatar/" + user.email,
            user_is_guest: user.is_guest,
        }),
        html: true,
        trigger: "manual",
        top_offset: $("#userlist-title").offset().top + 15,
        fix_positions: true,
    });
    popover_element.popover("show");

    init_email_clipboard();
    load_medium_avatar(user, $(".popover-avatar"));
}

// exporting for testability
exports._test_calculate_info_popover_placement = calculate_info_popover_placement;

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function show_user_info_popover_for_message(element, user, message) {
    const last_popover_elem = current_message_info_popover_elem;
    exports.hide_all();
    if (last_popover_elem !== undefined && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    current_msg_list.select_id(message.id);
    const elt = $(element);
    if (elt.data("popover") === undefined) {
        if (user === undefined) {
            // This is never supposed to happen, not even for deactivated
            // users, so we'll need to debug this error if it occurs.
            blueslip.error("Bad sender in message" + message.sender_id);
            return;
        }

        const is_sender_popover = message.sender_id === user.user_id;
        render_user_info_popover(
            user,
            elt,
            is_sender_popover,
            true,
            "respond_personal_button",
            "message-info-popover",
            "right",
        );

        current_message_info_popover_elem = elt;
    }
}

function show_mobile_message_buttons_popover(element) {
    const last_popover_elem = current_mobile_message_buttons_popover_elem;
    exports.hide_all();
    if (last_popover_elem !== undefined && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    const $element = $(element);
    $element.popover({
        placement: "left",
        template: render_mobile_message_buttons_popover(),
        content: render_mobile_message_buttons_popover_content({
            is_in_private_narrow: narrow_state.narrowed_to_pms(),
        }),
        html: true,
        trigger: "manual",
    });
    $element.popover("show");

    current_mobile_message_buttons_popover_elem = $element;
}

exports.hide_mobile_message_buttons_popover = function () {
    if (current_mobile_message_buttons_popover_elem) {
        current_mobile_message_buttons_popover_elem.popover("destroy");
        current_mobile_message_buttons_popover_elem = undefined;
    }
};

exports.hide_user_profile = function () {
    $("#user-profile-modal").modal("hide");
};

exports.show_user_profile = function (user) {
    exports.hide_all();

    const dateFormat = new Intl.DateTimeFormat("default", {dateStyle: "long"});
    const field_types = page_params.custom_profile_field_types;
    const profile_data = page_params.custom_profile_fields
        .map((f) => get_custom_profile_field_data(user, f, field_types, dateFormat))
        .filter((f) => f.name !== undefined);

    const args = {
        full_name: user.full_name,
        email: people.get_visible_email(user),
        profile_data,
        user_avatar: "avatar/" + user.email + "/medium",
        is_me: people.is_current_user(user.email),
        date_joined: dateFormat.format(parseISO(user.date_joined)),
        last_seen: buddy_data.user_last_seen_time_status(user.user_id),
        show_email: settings_data.show_email(),
        user_time: people.get_user_time(user.user_id),
        user_type: people.get_user_type(user.user_id),
        user_is_guest: user.is_guest,
    };

    $("#user-profile-modal-holder").html(render_user_profile_modal(args));
    $("#user-profile-modal").modal("show");

    settings_account.initialize_custom_user_type_fields(
        "#user-profile-modal #content",
        user.user_id,
        false,
        false,
    );
};

exports.show_user_info_popover = function (element, user) {
    const last_popover_elem = current_user_info_popover_elem;
    exports.hide_all();
    if (last_popover_elem !== undefined && last_popover_elem.get()[0] === element) {
        return;
    }
    const elt = $(element);
    render_user_info_popover(
        user,
        elt,
        false,
        false,
        "compose_private_message",
        "user-info-popover",
        "right",
    );
    current_user_info_popover_elem = elt;
};

function get_user_info_popover_for_message_items() {
    if (!current_message_info_popover_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = current_message_info_popover_elem.data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for actions menu.");
        return undefined;
    }

    return $("li:not(.divider):visible a", popover_data.$tip);
}

function get_user_info_popover_items() {
    const popover_elt = $("div.user-info-popover");
    if (!current_user_info_popover_elem || !popover_elt.length) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    if (popover_elt.length >= 2) {
        blueslip.error("More than one user info popovers cannot be opened at same time.");
        return undefined;
    }

    return $("li:not(.divider):visible a", popover_elt);
}

function fetch_group_members(member_ids) {
    return member_ids
        .map((m) => people.get_by_user_id(m))
        .filter((m) => m !== undefined)
        .map((p) => ({
            ...p,
            user_circle_class: buddy_data.get_user_circle_class(p.user_id),
            is_active: people.is_active_user_for_popover(p.user_id),
            user_last_seen_time_status: buddy_data.user_last_seen_time_status(p.user_id),
        }));
}

function sort_group_members(members) {
    return members.sort((a, b) => a.full_name.localeCompare(b.full_name));
}

// exporting these functions for testing purposes
exports._test_fetch_group_members = fetch_group_members;
exports._test_sort_group_members = sort_group_members;

// element is the target element to pop off of
// user is the user whose profile to show
// message is the message containing it, which should be selected
function show_user_group_info_popover(element, group, message) {
    const last_popover_elem = current_message_info_popover_elem;
    // hardcoded pixel height of the popover
    // note that the actual size varies (in group size), but this is about as big as it gets
    const popover_size = 390;
    exports.hide_all();
    if (last_popover_elem !== undefined && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    current_msg_list.select_id(message.id);
    const elt = $(element);
    if (elt.data("popover") === undefined) {
        const args = {
            group_name: group.name,
            group_description: group.description,
            members: sort_group_members(fetch_group_members(Array.from(group.members))),
        };
        elt.popover({
            placement: calculate_info_popover_placement(popover_size, elt),
            template: render_user_group_info_popover({class: "message-info-popover"}),
            content: render_user_group_info_popover_content(args),
            html: true,
            trigger: "manual",
        });
        elt.popover("show");
        current_message_info_popover_elem = elt;
    }
}

exports.toggle_actions_popover = function (element, id) {
    const last_popover_elem = current_actions_popover_elem;
    exports.hide_all();
    if (last_popover_elem !== undefined && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }

    $(element).closest(".message_row").toggleClass("has_popover has_actions_popover");
    current_msg_list.select_id(id);
    const elt = $(element);
    if (elt.data("popover") === undefined) {
        const message = current_msg_list.get(id);
        const editability = message_edit.get_editability(message);
        let use_edit_icon;
        let editability_menu_item;
        if (editability === message_edit.editability_types.FULL) {
            use_edit_icon = true;
            editability_menu_item = i18n.t("Edit");
        } else if (editability === message_edit.editability_types.TOPIC_ONLY) {
            use_edit_icon = false;
            editability_menu_item = i18n.t("View source / Edit topic");
        } else {
            use_edit_icon = false;
            editability_menu_item = i18n.t("View source");
        }
        const topic = message.topic;
        const can_mute_topic =
            message.stream && topic && !muting.is_topic_muted(message.stream_id, topic);
        const can_unmute_topic =
            message.stream && topic && muting.is_topic_muted(message.stream_id, topic);

        const should_display_edit_history_option =
            message.edit_history &&
            message.edit_history.some(
                (entry) =>
                    entry.prev_content !== undefined ||
                    util.get_edit_event_prev_topic(entry) !== undefined,
            ) &&
            page_params.realm_allow_edit_history;

        // Disabling this for /me messages is a temporary workaround
        // for the fact that we don't have a styling for how that
        // should look.  See also condense.js.
        const should_display_collapse =
            !message.locally_echoed && !message.is_me_message && !message.collapsed;
        const should_display_uncollapse =
            !message.locally_echoed && !message.is_me_message && message.collapsed;

        const should_display_edit_and_view_source =
            message.content !== "<p>(deleted)</p>" ||
            editability === message_edit.editability_types.FULL ||
            editability === message_edit.editability_types.TOPIC_ONLY;
        const should_display_quote_and_reply = message.content !== "<p>(deleted)</p>";

        const conversation_time_uri = hash_util
            .by_conversation_and_time_uri(message)
            .replace(/\(/g, "%28")
            .replace(/\)/g, "%29");

        const should_display_delete_option = message_edit.get_deletability(message);
        const args = {
            message_id: message.id,
            historical: message.historical,
            stream_id: message.stream_id,
            topic,
            use_edit_icon,
            editability_menu_item,
            can_mute_topic,
            can_unmute_topic,
            should_display_collapse,
            should_display_uncollapse,
            should_display_add_reaction_option: message.sent_by_me,
            should_display_edit_history_option,
            conversation_time_uri,
            narrowed: narrow_state.active(),
            should_display_delete_option,
            should_display_reminder_option: feature_flags.reminders_in_message_action_menu,
            should_display_edit_and_view_source,
            should_display_quote_and_reply,
        };

        const ypos = elt.offset().top;
        elt.popover({
            // Popover height with 7 items in it is ~190 px
            placement: message_viewport.height() - ypos < 220 ? "top" : "bottom",
            title: "",
            content: render_actions_popover_content(args),
            html: true,
            trigger: "manual",
        });
        elt.popover("show");
        current_actions_popover_elem = elt;
    }
};

exports.render_actions_remind_popover = function (element, id) {
    exports.hide_all();
    $(element).closest(".message_row").toggleClass("has_popover has_actions_popover");
    current_msg_list.select_id(id);
    const elt = $(element);
    if (elt.data("popover") === undefined) {
        const message = current_msg_list.get(id);
        const args = {
            message,
        };
        const ypos = elt.offset().top;
        elt.popover({
            // Popover height with 7 items in it is ~190 px
            placement: message_viewport.height() - ypos < 220 ? "top" : "bottom",
            title: "",
            content: render_remind_me_popover_content(args),
            html: true,
            trigger: "manual",
        });
        elt.popover("show");
        current_flatpickr_instance = $(
            `.remind.custom[data-message-id="${CSS.escape(message.id)}"]`,
        ).flatpickr({
            enableTime: true,
            clickOpens: false,
            defaultDate: "today",
            minDate: "today",
            plugins: [new ConfirmDatePlugin({})],
        });
        current_actions_popover_elem = elt;
    }
};

function get_action_menu_menu_items() {
    if (!current_actions_popover_elem) {
        blueslip.error("Trying to get menu items when action popover is closed.");
        return undefined;
    }

    const popover_data = current_actions_popover_elem.data("popover");
    if (!popover_data) {
        blueslip.error("Cannot find popover data for actions menu.");
        return undefined;
    }

    return $("li:not(.divider):visible a", popover_data.$tip);
}

exports.focus_first_popover_item = (items) => {
    if (!items) {
        return;
    }

    items.eq(0).expectOne().trigger("focus");
};

exports.popover_items_handle_keyboard = (key, items) => {
    if (!items) {
        return;
    }

    let index = items.index(items.filter(":focus"));

    if (key === "enter" && index >= 0 && index < items.length) {
        items[index].click();
        return;
    }
    if (index === -1) {
        index = 0;
    } else if ((key === "down_arrow" || key === "vim_down") && index < items.length - 1) {
        index += 1;
    } else if ((key === "up_arrow" || key === "vim_up") && index > 0) {
        index -= 1;
    }
    items.eq(index).trigger("focus");
};

function focus_first_action_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const items = get_action_menu_menu_items();
    exports.focus_first_popover_item(items);
}

exports.open_message_menu = function (message) {
    if (message.locally_echoed) {
        // Don't open the popup for locally echoed messages for now.
        // It creates bugs with things like keyboard handlers when
        // we get the server response.
        return true;
    }

    const message_id = message.id;
    exports.toggle_actions_popover($(".selected_message .actions_hover")[0], message_id);
    if (current_actions_popover_elem) {
        focus_first_action_popover_item();
    }
    return true;
};

exports.actions_menu_handle_keyboard = function (key) {
    const items = get_action_menu_menu_items();
    exports.popover_items_handle_keyboard(key, items);
};

exports.actions_popped = function () {
    return current_actions_popover_elem !== undefined;
};

exports.hide_actions_popover = function () {
    if (exports.actions_popped()) {
        $(".has_popover").removeClass("has_popover has_actions_popover");
        current_actions_popover_elem.popover("destroy");
        current_actions_popover_elem = undefined;
    }
    if (current_flatpickr_instance !== undefined) {
        current_flatpickr_instance.destroy();
        current_flatpickr_instance = undefined;
    }
};

exports.message_info_popped = function () {
    return current_message_info_popover_elem !== undefined;
};

exports.hide_message_info_popover = function () {
    if (exports.message_info_popped()) {
        current_message_info_popover_elem.popover("destroy");
        current_message_info_popover_elem = undefined;
    }
};

exports.user_info_popped = function () {
    return current_user_info_popover_elem !== undefined;
};

exports.hide_user_info_popover = function () {
    if (exports.user_info_popped()) {
        current_user_info_popover_elem.popover("destroy");
        current_user_info_popover_elem = undefined;
    }
};

exports.hide_userlist_sidebar = function () {
    $(".app-main .column-right").removeClass("expanded");
};

exports.hide_pm_list_sidebar = function () {
    $(".app-main .column-left").removeClass("expanded");
};

exports.show_userlist_sidebar = function () {
    $(".app-main .column-right").addClass("expanded");
    resize.resize_page_components();
};

exports.show_pm_list_sidebar = function () {
    $(".app-main .column-left").addClass("expanded");
    resize.resize_page_components();
};

let current_user_sidebar_user_id;
let current_user_sidebar_popover;

exports.user_sidebar_popped = () => current_user_sidebar_popover !== undefined;

exports.hide_user_sidebar_popover = function () {
    if (exports.user_sidebar_popped()) {
        // this hide_* method looks different from all the others since
        // the presence list may be redrawn. Due to funkiness with jquery's .data()
        // this would confuse $.popover("destroy"), which looks at the .data() attached
        // to a certain element. We thus save off the .data("popover") in the
        // show_user_sidebar_popover and inject it here before calling destroy.
        $("#user_presences").data("popover", current_user_sidebar_popover);
        $("#user_presences").popover("destroy");
        current_user_sidebar_user_id = undefined;
        current_user_sidebar_popover = undefined;
    }
};

function focus_user_info_popover_item() {
    // For now I recommend only calling this when the user opens the menu with a hotkey.
    // Our popup menus act kind of funny when you mix keyboard and mouse.
    const items = get_user_info_popover_for_message_items();
    exports.focus_first_popover_item(items);
}

function get_user_sidebar_popover_items() {
    if (!current_user_sidebar_popover) {
        blueslip.error("Trying to get menu items when user sidebar popover is closed.");
        return undefined;
    }

    return $("li:not(.divider):visible > a", current_user_sidebar_popover.$tip);
}

exports.user_sidebar_popover_handle_keyboard = function (key) {
    const items = get_user_sidebar_popover_items();
    exports.popover_items_handle_keyboard(key, items);
};

exports.user_info_popover_for_message_handle_keyboard = function (key) {
    const items = get_user_info_popover_for_message_items();
    exports.popover_items_handle_keyboard(key, items);
};

exports.user_info_popover_handle_keyboard = function (key) {
    const items = get_user_info_popover_items();
    exports.popover_items_handle_keyboard(key, items);
};

exports.show_sender_info = function () {
    const $message = $(".selected_message");
    const $sender = $message.find(".sender_info_hover");

    const message = current_msg_list.get(rows.id($message));
    const user = people.get_by_user_id(message.sender_id);
    show_user_info_popover_for_message($sender[0], user, message);
    if (current_message_info_popover_elem) {
        focus_user_info_popover_item();
    }
};

// On mobile web, opening the keyboard can trigger a resize event
// (which in turn can trigger a scroll event).  This will have the
// side effect of closing popovers, which we don't want.  So we
// suppress the first hide from scrolling after a resize using this
// variable.
let suppress_scroll_hide = false;

exports.set_suppress_scroll_hide = function () {
    suppress_scroll_hide = true;
};

// Playground_info contains all the data we need to generate a popover of
// playground links for each code block. The element is the target element
// to pop off of.
exports.toggle_playground_link_popover = (element, playground_info) => {
    const last_popover_elem = current_playground_links_popover_elem;
    exports.hide_all();
    if (last_popover_elem !== undefined && last_popover_elem.get()[0] === element) {
        // We want it to be the case that a user can dismiss a popover
        // by clicking on the same element that caused the popover.
        return;
    }
    const elt = $(element);
    if (elt.data("popover") === undefined) {
        const ypos = elt.offset().top;
        elt.popover({
            // It's unlikely we'll have more than 3-4 playground links
            // for one language, so it should be OK to hardcode 120 here.
            placement: message_viewport.height() - ypos < 120 ? "top" : "bottom",
            title: "",
            content: render_playground_links_popover_content({playground_info}),
            html: true,
            trigger: "manual",
        });
        elt.popover("show");
        current_playground_links_popover_elem = elt;
    }
};

exports.hide_playground_links_popover = () => {
    if (current_playground_links_popover_elem !== undefined) {
        current_playground_links_popover_elem.popover("destroy");
        current_playground_links_popover_elem = undefined;
    }
};

exports.register_click_handlers = function () {
    $("#main_div").on("click", ".actions_hover", function (e) {
        const row = $(this).closest(".message_row");
        e.stopPropagation();
        exports.toggle_actions_popover(this, rows.id(row));
    });

    $("#main_div").on(
        "click",
        ".sender_name, .sender_name-in-status, .inline_profile_picture",
        function (e) {
            const row = $(this).closest(".message_row");
            e.stopPropagation();
            const message = current_msg_list.get(rows.id(row));
            const user = people.get_by_user_id(message.sender_id);
            show_user_info_popover_for_message(this, user, message);
        },
    );

    $("#main_div").on("click", ".user-mention", function (e) {
        const id_string = $(this).attr("data-user-id");
        // We fallback to email to handle legacy Markdown that was rendered
        // before we cut over to using data-user-id
        const email = $(this).attr("data-user-email");
        if (id_string === "*" || email === "*") {
            return;
        }
        const row = $(this).closest(".message_row");
        e.stopPropagation();
        const message = current_msg_list.get(rows.id(row));
        let user;
        if (id_string) {
            const user_id = Number.parseInt(id_string, 10);
            user = people.get_by_user_id(user_id);
        } else {
            user = people.get_by_email(email);
        }
        show_user_info_popover_for_message(this, user, message);
    });

    $("#main_div").on("click", ".user-group-mention", function (e) {
        const user_group_id = Number.parseInt($(this).attr("data-user-group-id"), 10);
        const row = $(this).closest(".message_row");
        e.stopPropagation();
        const message = current_msg_list.get(rows.id(row));
        const group = user_groups.get_user_group_from_id(user_group_id, true);
        if (group === undefined) {
            // This user group has likely been deleted.
            blueslip.info("Unable to find user group in message" + message.sender_id);
        } else {
            show_user_group_info_popover(this, group, message);
        }
    });

    $("#main_div, #preview_content").on("click", ".code_external_link", function (e) {
        const view_in_playground_button = $(this);
        const codehilite_div = $(this).closest(".codehilite");
        e.stopPropagation();
        const playground_info = settings_config.get_playground_info_for_languages(
            codehilite_div.data("code-language"),
        );
        // We do the code extraction here and set the target href combining the url_prefix
        // and the extracted code. Depending on whether the language has multiple playground
        // links configured, a popover is show.
        const extracted_code = codehilite_div.find("code").text();
        if (playground_info.length === 1) {
            const url_prefix = playground_info[0].url_prefix;
            view_in_playground_button.attr("href", url_prefix + encodeURIComponent(extracted_code));
        } else {
            for (const $playground of playground_info) {
                $playground.playground_url =
                    $playground.url_prefix + encodeURIComponent(extracted_code);
            }
            exports.toggle_playground_link_popover(this, playground_info);
        }
    });

    $("body").on("click", ".popover_playground_link", (e) => {
        exports.hide_playground_links_popover();
        e.stopPropagation();
    });

    $("body").on("click", ".info_popover_actions .narrow_to_private_messages", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        exports.hide_all();
        if (overlays.settings_open()) {
            overlays.close_overlay("settings");
        }
        narrow.by("pm-with", email, {trigger: "user sidebar popover"});
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".info_popover_actions .narrow_to_messages_sent", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        exports.hide_all();
        if (overlays.settings_open()) {
            overlays.close_overlay("settings");
        }
        narrow.by("sender", email, {trigger: "user sidebar popover"});
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
        exports.hide_user_sidebar_popover();
        exports.hide_userlist_sidebar();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".message-info-popover .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_actions.respond_to_message({trigger: "user sidebar popover"});
        }
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        exports.hide_message_info_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".info_popover_actions .view_full_user_profile", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        exports.show_user_profile(user);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".info_popover_actions .clear_status", (e) => {
        e.preventDefault();
        const me = elem_to_user_id($(e.target).parents("ul"));
        user_status.server_update({
            user_id: me,
            status_text: "",
            success() {
                $(".info_popover_actions #status_message").html("");
            },
        });
    });

    $("body").on("click", ".view_user_profile", (e) => {
        const user_id = Number.parseInt($(e.target).attr("data-user-id"), 10);
        const user = people.get_by_user_id(user_id);
        exports.show_user_info_popover(e.target, user);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", "#user-profile-modal #name #edit-button", () => {
        exports.hide_user_profile();
    });

    $("body").on("click", ".compose_mobile_button", function (e) {
        show_mobile_message_buttons_popover(this);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".set_away_status", (e) => {
        exports.hide_all();
        user_status.server_set_away();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".revoke_away_status", (e) => {
        exports.hide_all();
        user_status.server_revoke_away();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".update_status_text", (e) => {
        exports.hide_all();

        user_status_ui.open_overlay();

        e.stopPropagation();
        e.preventDefault();
    });

    $("#user_presences").on("click", ".user-list-sidebar-menu-icon", function (e) {
        e.stopPropagation();

        // use email of currently selected user, rather than some elem comparison,
        // as the presence list may be redrawn with new elements.
        const target = $(this).closest("li");
        const user_id = elem_to_user_id(target.find("a"));

        if (current_user_sidebar_user_id === user_id) {
            // If the popover is already shown, clicking again should toggle it.
            // We don't want to hide the sidebars on smaller browser windows.
            exports.hide_all_except_sidebars();
            return;
        }
        exports.hide_all();

        if (userlist_placement === "right") {
            exports.show_userlist_sidebar();
        } else {
            // Maintain the same behavior when displaying with the streamlist.
            stream_popover.show_streamlist_sidebar();
        }

        const user = people.get_by_user_id(user_id);
        const popover_placement = userlist_placement === "left" ? "right" : "left";

        render_user_info_popover(
            user,
            target,
            false,
            false,
            "compose_private_message",
            "user_popover",
            popover_placement,
        );

        current_user_sidebar_user_id = user.user_id;
        current_user_sidebar_popover = target.data("popover");
    });

    $("body").on("mouseenter", ".user_popover_email", function () {
        const tooltip_holder = $(this).find("div");

        if (this.offsetWidth < this.scrollWidth) {
            tooltip_holder.addClass("display-tooltip");
        } else {
            tooltip_holder.removeClass("display-tooltip");
        }
    });

    $("body").on("click", ".respond_button", (e) => {
        // Arguably, we should fetch the message ID to respond to from
        // e.target, but that should always be the current selected
        // message in the current message list (and
        // compose_actions.respond_to_message doesn't take a message
        // argument).
        compose_actions.quote_and_reply({trigger: "popover respond"});
        exports.hide_actions_popover();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".reminder_button", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        exports.render_actions_remind_popover($(".selected_message .actions_hover")[0], message_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".remind.custom", (e) => {
        $(e.currentTarget)[0]._flatpickr.toggle();
        e.stopPropagation();
        e.preventDefault();
    });

    function reminder_click_handler(datestr, e) {
        const message_id = $(".remind.custom").data("message-id");
        reminder.do_set_reminder_for_message(message_id, datestr);
        exports.hide_all();
        e.stopPropagation();
        e.preventDefault();
    }

    $("body").on("click", ".remind.in_20m", (e) => {
        const datestr = formatISO(add(new Date(), {minutes: 20}));
        reminder_click_handler(datestr, e);
    });

    $("body").on("click", ".remind.in_1h", (e) => {
        const datestr = formatISO(add(new Date(), {hours: 1}));
        reminder_click_handler(datestr, e);
    });

    $("body").on("click", ".remind.in_3h", (e) => {
        const datestr = formatISO(add(new Date(), {hours: 3}));
        reminder_click_handler(datestr, e);
    });

    $("body").on("click", ".remind.tomo", (e) => {
        const datestr = formatISO(
            set(add(new Date(), {days: 1}), {hours: 9, minutes: 0, seconds: 0}),
        );
        reminder_click_handler(datestr, e);
    });

    $("body").on("click", ".remind.nxtw", (e) => {
        const datestr = formatISO(
            set(add(new Date(), {weeks: 1}), {hours: 9, minutes: 0, seconds: 0}),
        );
        reminder_click_handler(datestr, e);
    });

    $("body").on("click", ".flatpickr-calendar", (e) => {
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".flatpickr-confirm", (e) => {
        const datestr = $(".remind.custom")[0].value;
        reminder_click_handler(datestr, e);
    });

    $("body").on("click", ".respond_personal_button, .compose_private_message", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const email = people.get_by_user_id(user_id).email;
        compose_actions.start("private", {
            trigger: "popover send private",
            private_message_recipient: email,
        });
        exports.hide_all();
        if (overlays.settings_open()) {
            overlays.close_overlay("settings");
        }
        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".popover_toggle_collapse", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        const row = current_msg_list.get_row(message_id);
        const message = current_msg_list.get(rows.id(row));

        exports.hide_actions_popover();

        if (row) {
            if (message.collapsed) {
                condense.uncollapse(row);
            } else {
                condense.collapse(row);
            }
        }

        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".popover_edit_message", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        const row = current_msg_list.get_row(message_id);
        exports.hide_actions_popover();
        message_edit.start(row);
        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".view_edit_history", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        const row = current_msg_list.get_row(message_id);
        const message = current_msg_list.get(rows.id(row));
        const message_history_cancel_btn = $("#message-history-cancel");

        exports.hide_actions_popover();
        message_edit_history.show_history(message);
        message_history_cancel_btn.trigger("focus");
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".popover_mute_topic", (e) => {
        const stream_id = Number.parseInt($(e.currentTarget).attr("data-msg-stream-id"), 10);
        const topic = $(e.currentTarget).attr("data-msg-topic");

        exports.hide_actions_popover();
        muting_ui.mute_topic(stream_id, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".popover_unmute_topic", (e) => {
        const stream_id = Number.parseInt($(e.currentTarget).attr("data-msg-stream-id"), 10);
        const topic = $(e.currentTarget).attr("data-msg-topic");

        exports.hide_actions_popover();
        muting_ui.unmute_topic(stream_id, topic);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".delete_message", (e) => {
        const message_id = $(e.currentTarget).data("message-id");
        exports.hide_actions_popover();
        message_edit.delete_message(message_id);
        e.stopPropagation();
        e.preventDefault();
    });

    new ClipboardJS(".copy_link");

    $("body").on("click", ".copy_link", function (e) {
        exports.hide_actions_popover();
        const message_id = $(this).attr("data-message-id");
        const row = $(`[zid='${CSS.escape(message_id)}']`);
        row.find(".alert-msg")
            .text(i18n.t("Copied!"))
            .css("display", "block")
            .delay(1000)
            .fadeOut(300);

        setTimeout(() => {
            // The Cliboard library works by focusing to a hidden textarea.
            // We unfocus this so keyboard shortcuts, etc., will work again.
            $(":focus").trigger("blur");
        }, 0);

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".deactivate_user_from_popup_info", (e) => {
        exports.hide_all();

        function confirm_deactivation() {
            $("#confirm_user_deactivation_modal").modal("hide");
            const user_id = elem_to_user_id($(e.target).parents("ul"));
            const url = "/json/users/" + encodeURIComponent(user_id);
            const request_method = channel.del;
            request_method({
                url,
            });
        }

        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);

        $("#confirm_user_deactivation_modal_holder").html(render_confirm_user_deactivation_modal());
        $("#confirm_user_deactivation_modal").find(".user_name").text(user.full_name);
        $("#confirm_user_deactivation_modal").find(".email").text(user.email);
        $("#confirm_user_deactivation_modal").on(
            "click",
            ".confirm_user_deactivation_button",
            confirm_deactivation,
        );
        $("#confirm_user_deactivation_modal").modal("show");

        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".reactivate_user_from_popup_info", (e) => {
        const user_id = elem_to_user_id($(e.target).parents("ul"));
        const url = "/json/users/" + encodeURIComponent(user_id) + "/reactivate";
        const request_method = channel.post;
        request_method({
            url,
        });
        exports.hide_all();

        e.stopPropagation();
        e.preventDefault();
    });

    new ClipboardJS(".copy_mention_syntax");

    $("body").on("click", ".copy_mention_syntax", (e) => {
        exports.hide_all();
        e.stopPropagation();
        e.preventDefault();
    });

    (function () {
        let last_scroll = 0;

        $(".app").on("scroll", () => {
            if (suppress_scroll_hide) {
                suppress_scroll_hide = false;
                return;
            }

            const date = Date.now();

            // only run `popovers.hide_all()` if the last scroll was more
            // than 250ms ago.
            if (date - last_scroll > 250) {
                exports.hide_all();
            }

            // update the scroll time on every event to make sure it doesn't
            // retrigger `hide_all` while still scrolling.
            last_scroll = date;
        });
    })();
};

exports.any_active = function () {
    // True if any popover (that this module manages) is currently shown.
    // Expanded sidebars on mobile view count as popovers as well.
    return (
        exports.actions_popped() ||
        exports.user_sidebar_popped() ||
        stream_popover.stream_popped() ||
        stream_popover.topic_popped() ||
        exports.message_info_popped() ||
        exports.user_info_popped() ||
        emoji_picker.reactions_popped() ||
        $("[class^='column-'].expanded").length
    );
};

// This function will hide all true popovers (the streamlist and
// userlist sidebars use the popover infrastructure, but doesn't work
// like a popover structurally).
exports.hide_all_except_sidebars = function () {
    $(".has_popover").removeClass("has_popover has_actions_popover has_emoji_popover");
    exports.hide_actions_popover();
    exports.hide_message_info_popover();
    emoji_picker.hide_emoji_popover();
    stream_popover.hide_stream_popover();
    stream_popover.hide_topic_popover();
    stream_popover.hide_all_messages_popover();
    stream_popover.hide_starred_messages_popover();
    exports.hide_user_sidebar_popover();
    exports.hide_mobile_message_buttons_popover();
    exports.hide_user_profile();
    exports.hide_user_info_popover();
    exports.hide_playground_links_popover();

    // look through all the popovers that have been added and removed.
    for (const $o of list_of_popovers) {
        if (!document.body.contains($o.$element[0]) && $o.$tip) {
            $o.$tip.remove();
        }
    }
    list_of_popovers = [];
};

// This function will hide all the popovers, including the mobile web
// or narrow window sidebars.
exports.hide_all = function () {
    exports.hide_userlist_sidebar();
    stream_popover.hide_streamlist_sidebar();
    exports.hide_all_except_sidebars();
};

exports.set_userlist_placement = function (placement) {
    userlist_placement = placement || "right";
};

exports.compute_placement = function (
    elt,
    popover_height,
    popover_width,
    prefer_vertical_positioning,
) {
    const client_rect = elt.get(0).getBoundingClientRect();
    const distance_from_top = client_rect.top;
    const distance_from_bottom = message_viewport.height() - client_rect.bottom;
    const distance_from_left = client_rect.left;
    const distance_from_right = message_viewport.width() - client_rect.right;

    const elt_will_fit_horizontally =
        distance_from_left + elt.width() / 2 > popover_width / 2 &&
        distance_from_right + elt.width() / 2 > popover_width / 2;

    const elt_will_fit_vertically =
        distance_from_bottom + elt.height() / 2 > popover_height / 2 &&
        distance_from_top + elt.height() / 2 > popover_height / 2;

    // default to placing the popover in the center of the screen
    let placement = "viewport_center";

    // prioritize left/right over top/bottom
    if (distance_from_top > popover_height && elt_will_fit_horizontally) {
        placement = "top";
    }
    if (distance_from_bottom > popover_height && elt_will_fit_horizontally) {
        placement = "bottom";
    }

    if (prefer_vertical_positioning && placement !== "viewport_center") {
        // If vertical positioning is preferred and the popover fits in
        // either top or bottom position then return.
        return placement;
    }

    if (distance_from_left > popover_width && elt_will_fit_vertically) {
        placement = "left";
    }
    if (distance_from_right > popover_width && elt_will_fit_vertically) {
        placement = "right";
    }

    return placement;
};

window.popovers = exports;
