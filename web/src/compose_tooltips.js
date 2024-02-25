import $ from "jquery";
import _ from "lodash";
import {delegate} from "tippy.js";

import render_narrow_to_compose_recipients_tooltip from "../templates/narrow_to_compose_recipients_tooltip.hbs";

import * as compose_recipient from "./compose_recipient";
import * as compose_state from "./compose_state";
import * as compose_validate from "./compose_validate";
import {$t} from "./i18n";
import * as narrow_state from "./narrow_state";
import * as popover_menus from "./popover_menus";
import {EXTRA_LONG_HOVER_DELAY, INSTANT_HOVER_DELAY, LONG_HOVER_DELAY} from "./tippyjs";
import {parse_html} from "./ui_util";
import {user_settings} from "./user_settings";

export function initialize() {
    delegate("body", {
        target: [
            // Ideally this would be `#compose_buttons .button`, but the
            // reply button's actual area is its containing span.
            "#compose_buttons .compose-reply-button-wrapper",
            "#left_bar_compose_mobile_button_big",
            "#new_direct_message_button",
        ],
        delay: EXTRA_LONG_HOVER_DELAY,
        // Only show on mouseenter since for spectators, clicking on these
        // buttons opens login modal, and Micromodal returns focus to the
        // trigger after it closes, which results in tooltip being displayed.
        trigger: "mouseenter",
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: "#new_conversation_button",
        delay: EXTRA_LONG_HOVER_DELAY,
        // Only show on mouseenter since for spectators, clicking on these
        // buttons opens login modal, and Micromodal returns focus to the
        // trigger after it closes, which results in tooltip being displayed.
        trigger: "mouseenter",
        appendTo: () => document.body,
        onShow(instance) {
            const $elem = $(instance.reference);
            const conversation_type = $elem.attr("data-conversation-type");
            if (conversation_type === "direct") {
                instance.setContent(
                    parse_html($("#new_direct_message_button_tooltip_template").html()),
                );
                return;
            } else if (conversation_type === "stream") {
                instance.setContent(
                    parse_html($("#new_topic_message_button_tooltip_template").html()),
                );
                return;
            }
            // Use new_stream_message_button_tooltip_template when the
            // conversation_type is equal to "non-specific" and also as a default fallback.
            instance.setContent(
                parse_html($("#new_stream_message_button_tooltip_template").html()),
            );
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        // Only display Tippy content on classes accompanied by a `data-` attribute.
        target: `
        .compose_control_button[data-tooltip-template-id],
        .compose_control_button[data-tippy-content],
        .compose_control_button_container
        `,
        // Add some additional delay when they open
        // so that regular users don't have to see
        // them unless they want to.
        delay: LONG_HOVER_DELAY,
        // By default, tippyjs uses a trigger value of "mouseenter focus",
        // which means the tooltips can appear either when the element is
        // hovered over or when it receives focus (e.g. by being clicked).
        // However, we only want the tooltips to appear on hover, not on click.
        // Therefore, we need to remove the "focus" trigger from the buttons,
        // so that the tooltips don't appear when the buttons are clicked.
        trigger: "mouseenter",
        // This ensures that the upload files tooltip
        // doesn't hide behind the left sidebar.
        appendTo: () => document.body,
        // If the button is `.disabled-on-hover`, then we want to show the
        // tooltip instantly, to make it clear to the user that the button
        // is disabled, and why.
        onTrigger(instance, event) {
            if (event.currentTarget.classList.contains("disabled-on-hover")) {
                instance.setProps({delay: INSTANT_HOVER_DELAY});
            } else {
                instance.setProps({delay: LONG_HOVER_DELAY});
            }
        },
    });

    delegate("body", {
        target: ".send-control-button",
        delay: LONG_HOVER_DELAY,
        placement: "top",
        onShow() {
            // Don't show send-area tooltips if the popover is displayed.
            if (popover_menus.is_scheduled_messages_popover_displayed()) {
                return false;
            }
            return true;
        },
        appendTo: () => document.body,
    });

    delegate("body", {
        target: "#compose-send-button",
        delay: EXTRA_LONG_HOVER_DELAY,
        // By default, tippyjs uses a trigger value of "mouseenter focus",
        // but by specifying "mouseenter", this will prevent showing the
        // Send tooltip when tabbing to the Send button.
        trigger: "mouseenter",
        appendTo: () => document.body,
        onShow(instance) {
            // Don't show Send button tooltip if the popover is displayed.
            if (popover_menus.is_scheduled_messages_popover_displayed()) {
                return false;
            }
            if (user_settings.enter_sends) {
                instance.setContent(parse_html($("#send-enter-tooltip-template").html()));
            } else {
                instance.setContent(parse_html($("#send-ctrl-enter-tooltip-template").html()));
            }
            return true;
        },
    });

    delegate("body", {
        target: ".narrow_to_compose_recipients",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        content() {
            const narrow_filter = narrow_state.filter();
            let display_current_view;
            if (narrow_state.is_message_feed_visible()) {
                if (narrow_filter === undefined) {
                    display_current_view = $t({defaultMessage: "Currently viewing all messages."});
                } else if (
                    _.isEqual(narrow_filter.sorted_term_types(), ["stream"]) &&
                    compose_state.get_message_type() === "stream" &&
                    narrow_filter.operands("stream")[0] === compose_state.stream_name()
                ) {
                    display_current_view = $t({
                        defaultMessage: "Currently viewing the entire stream.",
                    });
                } else if (
                    _.isEqual(narrow_filter.sorted_term_types(), ["is-dm"]) &&
                    compose_state.get_message_type() === "private"
                ) {
                    display_current_view = $t({
                        defaultMessage: "Currently viewing all direct messages.",
                    });
                }
            }

            return parse_html(render_narrow_to_compose_recipients_tooltip({display_current_view}));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        // TODO: Might need to target just the Send button itself
        // in the new design
        target: [".disabled-message-send-controls"],
        maxWidth: 350,
        content: () =>
            compose_recipient.get_posting_policy_error_message() ||
            compose_validate.get_disabled_send_tooltip(),
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });
}
