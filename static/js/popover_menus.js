/* Module for popovers that have been ported to the modern
   TippyJS/Popper popover library from the legacy Bootstrap
   popovers system in popovers.js. */

import $ from "jquery";
import {delegate} from "tippy.js";

import render_actions_popover_content from "../templates/actions_popover_content.hbs";
import render_left_sidebar_stream_setting_popover from "../templates/left_sidebar_stream_setting_popover.hbs";
import render_mobile_message_buttons_popover_content from "../templates/mobile_message_buttons_popover_content.hbs";

import * as compose_actions from "./compose_actions";
import * as condense from "./condense";
import * as emoji_picker from "./emoji_picker";
import * as feature_flags from "./feature_flags";
import * as hash_util from "./hash_util";
import {$t} from "./i18n";
import * as message_edit from "./message_edit";
import * as message_edit_history from "./message_edit_history";
import * as message_lists from "./message_lists";
import * as muted_topics from "./muted_topics";
import * as muted_topics_ui from "./muted_topics_ui";
import * as muted_users from "./muted_users";
import * as narrow_state from "./narrow_state";
import {page_params} from "./page_params";
import * as popovers from "./popovers";
import * as rows from "./rows";
import * as settings_data from "./settings_data";
import * as util from "./util";

let left_sidebar_stream_setting_popover_displayed = false;
let compose_mobile_button_popover_displayed = false;
let message_actions_popover_visible = false;

const default_popover_props = {
    delay: 0,
    appendTo: () => document.body,
    trigger: "click",
    allowHTML: true,
    interactive: true,
    hideOnClick: true,
    /* The light-border TippyJS theme is a bit of a misnomer; it
       is a popover styling similar to Bootstrap.  We've also customized
       its CSS to support Zulip's night theme. */
    theme: "light-border",
    touch: true,
};

export function is_left_sidebar_stream_setting_popover_displayed() {
    return left_sidebar_stream_setting_popover_displayed;
}

export function is_compose_mobile_button_popover_displayed() {
    return compose_mobile_button_popover_displayed;
}

export function message_actions_popped() {
    return message_actions_popover_visible;
}

export function initialize() {
    delegate("body", {
        ...default_popover_props,
        target: "#streams_inline_cog",
        onShow(instance) {
            popovers.hide_all_except_sidebars(instance);
            instance.setContent(
                render_left_sidebar_stream_setting_popover({
                    can_create_streams: settings_data.user_can_create_streams(),
                }),
            );
            left_sidebar_stream_setting_popover_displayed = true;
            $(instance.popper).one("click", instance.hide);
        },
        onHidden() {
            left_sidebar_stream_setting_popover_displayed = false;
        },
    });

    // compose box buttons popover shown on mobile widths.
    delegate("body", {
        ...default_popover_props,
        target: ".compose_mobile_button",
        placement: "top",
        onShow(instance) {
            popovers.hide_all_except_sidebars(instance);
            instance.setContent(
                render_mobile_message_buttons_popover_content({
                    is_in_private_narrow: narrow_state.narrowed_to_pms(),
                }),
            );
            compose_mobile_button_popover_displayed = true;

            const $popper = $(instance.popper);
            $popper.one("click", instance.hide);
            $popper.one("click", ".compose_mobile_stream_button", () => {
                compose_actions.start("stream", {trigger: "new topic button"});
            });
            $popper.one("click", ".compose_mobile_private_button", () => {
                compose_actions.start("private");
            });
        },
        onHidden(instance) {
            // Destroy instance so that event handlers
            // are destroyed too.
            instance.destroy();
            compose_mobile_button_popover_displayed = false;
        },
    });

    // Message actions popover.
    delegate("body", {
        ...default_popover_props,
        target: ".actions_hover i.zulip-icon-ellipsis-v-solid",
        placement: "bottom",
        onShow(instance) {
            popovers.hide_all_except_sidebars(instance);
            const $elt = $(instance.reference);
            const row = $elt.closest(".message_row");
            row.toggleClass("has_popover has_actions_popover");
            const id = rows.id(row);
            message_lists.current.select_id(id);

            const message = message_lists.current.get(id);
            const message_id = message.id;
            const message_container = message_lists.current.view.message_containers.get(message_id);
            const should_display_hide_option =
                muted_users.is_user_muted(message.sender_id) && !message_container.is_hidden;
            const editability = message_edit.get_editability(message);
            let use_edit_icon;
            let editability_menu_item;
            if (editability === message_edit.editability_types.FULL) {
                use_edit_icon = true;
                editability_menu_item = $t({defaultMessage: "Edit"});
            } else if (editability === message_edit.editability_types.TOPIC_ONLY) {
                use_edit_icon = false;
                editability_menu_item = $t({defaultMessage: "View source / Edit topic"});
            } else {
                use_edit_icon = false;
                editability_menu_item = $t({defaultMessage: "View source"});
            }
            const topic = message.topic;
            const can_mute_topic =
                message.stream && topic && !muted_topics.is_topic_muted(message.stream_id, topic);
            const can_unmute_topic =
                message.stream && topic && muted_topics.is_topic_muted(message.stream_id, topic);

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

            const conversation_time_uri = hash_util.by_conversation_and_time_uri(message);

            const should_display_delete_option = message_edit.get_deletability(message);
            const args = {
                message_id,
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
                should_display_hide_option,
                conversation_time_uri,
                narrowed: narrow_state.active(),
                should_display_delete_option,
                should_display_reminder_option: feature_flags.reminders_in_message_action_menu,
                should_display_edit_and_view_source,
                should_display_quote_and_reply,
            };

            instance.setContent(render_actions_popover_content(args));
            message_actions_popover_visible = true;

            const $popper = $(instance.popper);

            // Hide popover on clicking of the options.
            $popper.one("click", instance.hide);

            $popper.one("click", ".rehide_muted_user_message", (e) => {
                const row = message_lists.current.get_row(message_id);
                if (row && !message_container.is_hidden) {
                    message_lists.current.view.hide_revealed_message(message_id);
                }
                e.preventDefault();
            });

            $popper.one("click", ".popover_edit_message", (e) => {
                const row = message_lists.current.get_row(message_id);
                message_edit.start(row);
                e.preventDefault();
            });

            $popper.one("click", ".respond_button", (e) => {
                // Arguably, we should fetch the message ID to respond to from
                // e.target, but that should always be the current selected
                // message in the current message list (and
                // compose_actions.respond_to_message doesn't take a message
                // argument).
                compose_actions.quote_and_reply({trigger: "popover respond"});
                e.preventDefault();
            });

            $popper.one("click", ".reminder_button", (e) => {
                popovers.render_actions_remind_popover(
                    $(".selected_message .actions_hover")[0],
                    message_id,
                );
                e.preventDefault();
            });

            $popper.one("click", ".popover_toggle_collapse", (e) => {
                const row = message_lists.current.get_row(message_id);
                if (row) {
                    if (message.collapsed) {
                        condense.uncollapse(row);
                    } else {
                        condense.collapse(row);
                    }
                }
                e.preventDefault();
            });

            $popper.one("click", ".view_edit_history", (e) => {
                const message_history_cancel_btn = $("#message-history-cancel");

                message_edit_history.show_history(message);
                message_history_cancel_btn.trigger("focus");
                e.preventDefault();
            });

            $popper.one("click", ".delete_message", (e) => {
                message_edit.delete_message(message_id);
                e.preventDefault();
            });

            $popper.one("click", ".popover_mute_topic", (e) => {
                muted_topics_ui.mute_topic(message.stream_id, message.topic);
                e.preventDefault();
            });

            $popper.one("click", ".popover_unmute_topic", (e) => {
                muted_topics_ui.unmute_topic(message.stream_id, message.topic);
                e.preventDefault();
            });

            popovers.clipboard_enable(".copy_link").on("success", () => {
                // e.trigger returns the DOM element triggering the copy action
                const row = $(`[zid='${CSS.escape(message_id)}']`);
                row.find(".alert-msg")
                    .text($t({defaultMessage: "Copied!"}))
                    .css("display", "block")
                    .delay(1000)
                    .fadeOut(300);

                setTimeout(() => {
                    // The Cliboard library works by focusing to a hidden textarea.
                    // We unfocus this so keyboard shortcuts, etc., will work again.
                    $(":focus").trigger("blur");
                }, 0);
            });

            $popper.one("click", ".reaction_button", (e) => {
                e.preventDefault();
                instance.hide();
                setTimeout(() => {
                    emoji_picker.toggle_emoji_popover(instance.reference.parentElement, message_id);
                }, 0);
            });
        },
        onHidden(instance) {
            instance.destroy();
            message_actions_popover_visible = false;
        },
    });
}
