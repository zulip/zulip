import ClipboardJS from "clipboard";
import $ from "jquery";

import * as channel from "./channel";
import * as compose_actions from "./compose_actions";
import * as compose_reply from "./compose_reply";
import * as compose_state from "./compose_state";
import * as compose_ui from "./compose_ui";
import {show_copied_confirmation} from "./copied_tooltip";
import * as dialog_widget from "./dialog_widget";
import {$t_html} from "./i18n";
import * as message_lists from "./message_lists";
import * as muted_users from "./muted_users";
import * as narrow from "./narrow";
import * as overlays from "./overlays";
import * as people from "./people";
import {hide_all} from "./popovers";
import * as rows from "./rows";
import * as sidebar_ui from "./sidebar_ui";
import * as ui_report from "./ui_report";
import * as user_card_popover from "./user_card_popover";
import * as user_deactivation_ui from "./user_deactivation_ui";
import * as user_profile from "./user_profile";
import * as user_status from "./user_status";
import * as user_status_ui from "./user_status_ui";

function register_click_handlers() {
    $("#main_div").on("click", ".sender_name, .inline_profile_picture", function (e) {
        const $row = $(this).closest(".message_row");
        e.stopPropagation();
        const message = message_lists.current.get(rows.id($row));
        const user = people.get_by_user_id(message.sender_id);
        user_card_popover.toggle_user_card_popover_for_message(this, user, message);
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
        user_card_popover.toggle_user_card_popover_for_message(this, user, message);
    });

    $("body").on("click", ".user-card-popover-actions .narrow_to_private_messages", (e) => {
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
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
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
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
        const me = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
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
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
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
        user_deactivation_ui.confirm_reactivation(user_id, handle_confirm, true);
    });

    $("body").on("click", ".user-card-popover-actions .view_full_user_profile", (e) => {
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user);
        e.stopPropagation();
        e.preventDefault();
    });
    $("body").on("click", ".user-card-popover-root .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_actions.start("stream", {trigger: "sidebar user actions"});
        }
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        user_card_popover.user_sidebar.hide();
        sidebar_ui.hide_userlist_sidebar();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".message-user-card-popover-root .mention_user", (e) => {
        if (!compose_state.composing()) {
            compose_reply.respond_to_message({trigger: "user sidebar popover"});
        }
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        const name = people.get_by_user_id(user_id).full_name;
        const mention = people.get_mention_syntax(name, user_id);
        compose_ui.insert_syntax_and_focus(mention);
        user_card_popover.message_user_card.hide();
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".view_user_profile", (e) => {
        const user_id = Number.parseInt($(e.currentTarget).attr("data-user-id"), 10);
        const user = people.get_by_user_id(user_id);
        user_card_popover.toggle_user_card_popover(e.target, user);
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

    $("#user_presences").on("click", ".user-list-sidebar-menu-icon", (e) => {
        e.stopPropagation();
        const $target = $(e.currentTarget).closest("li");

        user_card_popover.toggle_sidebar_user_card_popover($target);
    });

    $("body").on("click", ".sidebar-popover-mute-user", (e) => {
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        user_card_popover.hide_all_user_card_popovers();
        e.stopPropagation();
        e.preventDefault();
        user_card_popover.confirm_mute_user(user_id);
    });

    $("body").on("click", ".sidebar-popover-unmute-user", (e) => {
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        user_card_popover.hide_all_user_card_popovers();
        muted_users.unmute_user(user_id);
        e.stopPropagation();
        e.preventDefault();
    });

    $("body").on("click", ".respond_personal_button, .compose_private_message", (e) => {
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
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
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        user_profile.show_user_profile(user, "manage-profile-tab");
    });

    $("body").on("click", ".user-card-popover-manage-menu-btn", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const user_id = user_card_popover.elem_to_user_id($(e.target).parents("ul"));
        const user = people.get_by_user_id(user_id);
        user_card_popover.toggle_user_card_popover_manage_menu(e.target, user);
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
    new ClipboardJS(".copy_mention_syntax");
}
