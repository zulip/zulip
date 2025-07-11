import $ from "jquery";
import _ from "lodash";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_drafts_tooltip from "../templates/drafts_tooltip.hbs";
import render_narrow_to_compose_recipients_tooltip from "../templates/narrow_to_compose_recipients_tooltip.hbs";

import * as blueslip from "./blueslip.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_validate from "./compose_validate.ts";
import {$t} from "./i18n.ts";
import {pick_empty_narrow_banner} from "./narrow_banner.ts";
import * as narrow_state from "./narrow_state.ts";
import * as popover_menus from "./popover_menus.ts";
import {realm} from "./state_data.ts";
import {
    EXTRA_LONG_HOVER_DELAY,
    INSTANT_HOVER_DELAY,
    LONG_HOVER_DELAY,
    SINGLETON_INSTANT_HOVER_DELAY,
    SINGLETON_LONG_HOVER_DELAY,
    get_tooltip_content,
} from "./tippyjs.ts";
import {parse_html} from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

type SingletonContext = "compose" | `edit_message:${string}`;
type SingletonTooltips = {
    tooltip_instances: tippy.Instance[] | null;
    singleton_instance: tippy.CreateSingletonInstance | null;
};

const compose_button_singleton_context_map = new Map<SingletonContext, SingletonTooltips>();

// Ensure proper teardown of singleton instances, especially for "Save/Cancel" actions or when handling edit window time limits.
// Reference: http://atomiks.github.io/tippyjs/v6/addons/#destroy
export function clean_up_compose_singleton_tooltip(context: SingletonContext): void {
    const singleton_tooltips = compose_button_singleton_context_map.get(context);
    if (singleton_tooltips) {
        singleton_tooltips.singleton_instance?.destroy();
        if (singleton_tooltips.tooltip_instances) {
            for (const tippy_instance of singleton_tooltips.tooltip_instances) {
                if (!tippy_instance.state.isDestroyed) {
                    tippy_instance.destroy();
                }
            }
        }
        compose_button_singleton_context_map.delete(context);
    }
}

export function initialize_compose_tooltips(context: SingletonContext, selector: string): void {
    // Clean up existing instances first
    clean_up_compose_singleton_tooltip(context);

    const tooltip_instances = tippy.default(selector, {
        trigger: "mouseenter",
        appendTo: () => document.body,
        placement: "top",
    });

    const singleton_instance = tippy.createSingleton(tooltip_instances, {
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onTrigger(instance, event) {
            const currentTarget = event.currentTarget;
            if (currentTarget instanceof HTMLElement) {
                const content = get_tooltip_content(currentTarget);
                if (content) {
                    instance.setContent(content);
                }
                if (currentTarget.classList?.contains("disabled-on-hover")) {
                    instance.setProps({delay: SINGLETON_INSTANT_HOVER_DELAY});
                } else {
                    instance.setProps({delay: SINGLETON_LONG_HOVER_DELAY});
                }
            }
        },
    });

    compose_button_singleton_context_map.set(context, {
        tooltip_instances,
        singleton_instance,
    });
}

export function initialize(): void {
    tippy.delegate("body", {
        target: [
            // Ideally this would be `#compose_buttons .button`, but the
            // reply button's actual area is its containing span.
            "#left_bar_compose_mobile_button_big",
            "#new_direct_message_button",
        ].join(","),
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
    tippy.delegate("body", {
        target: "#compose_buttons .compose-reply-button-wrapper",
        delay: EXTRA_LONG_HOVER_DELAY,
        // Only show on mouseenter since for spectators, clicking on these
        // buttons opens login modal, and Micromodal returns focus to the
        // trigger after it closes, which results in tooltip being displayed.
        trigger: "mouseenter",
        appendTo: () => document.body,
        onShow(instance) {
            const $elem = $(instance.reference);
            const button_type = $elem.attr("data-reply-button-type");
            switch (button_type) {
                case "direct_disabled": {
                    const narrow_filter = narrow_state.filter();
                    assert(narrow_filter !== undefined);
                    instance.setContent(pick_empty_narrow_banner(narrow_filter).title);
                    return;
                }
                case "stream_disabled": {
                    instance.setContent(
                        parse_html(
                            $("#compose_disable_stream_reply_button_tooltip_template").html(),
                        ),
                    );
                    return;
                }
                case "selected_message": {
                    instance.setContent(
                        parse_html($("#compose_reply_message_button_tooltip_template").html()),
                    );
                    return;
                }
                case "selected_conversation": {
                    instance.setContent(
                        parse_html(
                            $("#compose_reply_selected_topic_button_tooltip_template").html(),
                        ),
                    );
                    return;
                }
                default: {
                    instance.setContent(
                        parse_html($("#compose_reply_message_button_tooltip_template").html()),
                    );
                    return;
                }
            }
        },
        onTrigger(instance, event) {
            assert(event.currentTarget instanceof HTMLElement);
            if ($(event.currentTarget).attr("data-reply-button-type") === "stream_disabled") {
                instance.setProps({delay: INSTANT_HOVER_DELAY});
            }
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: "#compose_buttons .compose_new_conversation_button",
        delay: EXTRA_LONG_HOVER_DELAY,
        // Only show on mouseenter since for spectators, clicking on these
        // buttons opens login modal, and Micromodal returns focus to the
        // trigger after it closes, which results in tooltip being displayed.
        trigger: "mouseenter",
        appendTo: () => document.body,
        onShow(instance) {
            const $new_conversation_button = $("#new_conversation_button");
            const conversation_type = $new_conversation_button.attr("data-conversation-type");
            if (conversation_type === "stream") {
                if ($new_conversation_button.prop("disabled")) {
                    instance.setContent(
                        parse_html(
                            $("#compose_disable_stream_reply_button_tooltip_template").html(),
                        ),
                    );
                } else {
                    instance.setContent(
                        parse_html($("#new_topic_message_button_tooltip_template").html()),
                    );
                }
                return undefined;
            }
            // Use new_stream_message_button_tooltip_template when the
            // conversation_type is equal to "non-specific" and also as a default fallback.
            instance.setContent(
                parse_html($("#new_stream_message_button_tooltip_template").html()),
            );
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".send-control-button",
        delay: LONG_HOVER_DELAY,
        placement: "top",
        onShow(instance) {
            // Don't show send-area tooltips if the popover is displayed.
            if (popover_menus.is_scheduled_messages_popover_displayed()) {
                return false;
            }
            if (instance.reference.id === "compose-drafts-button") {
                const count =
                    instance.reference.querySelector(".compose-drafts-count")!.textContent ?? 0;
                // Explain that the number in brackets is the number of drafts for this conversation.
                const draft_count_msg = $t(
                    {
                        defaultMessage:
                            "{count, plural, one {# draft} other {# drafts}} for this conversation",
                    },
                    {count},
                );
                instance.setContent(parse_html(render_drafts_tooltip({draft_count_msg})));
            }
            return undefined;
        },
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: "#compose-limit-indicator",
        delay: INSTANT_HOVER_DELAY,
        trigger: "mouseenter",
        appendTo: () => document.body,
        onShow(instance) {
            instance.setContent(
                $t(
                    {defaultMessage: `Maximum message length: {max_length} characters`},
                    {max_length: realm.max_message_length},
                ),
            );
        },
    });

    tippy.delegate("body", {
        target: "#compose-send-button",
        // 350px at 14px/1em
        maxWidth: "25em",
        // By default, tippyjs uses a trigger value of "mouseenter focus",
        // but by specifying "mouseenter", this will prevent showing the
        // Send tooltip when tabbing to the Send button.
        trigger: "mouseenter",
        appendTo: () => document.body,
        onTrigger(instance) {
            if (instance.reference.classList.contains("disabled-message-send-controls")) {
                instance.setProps({
                    delay: 0,
                });
            } else {
                instance.setProps({
                    delay: EXTRA_LONG_HOVER_DELAY,
                });
            }
        },
        onShow(instance) {
            // Don't show send-area tooltips if the popover is displayed.
            if (popover_menus.is_scheduled_messages_popover_displayed()) {
                return false;
            }

            if (instance.reference.classList.contains("disabled-message-send-controls")) {
                const error_message = compose_validate.get_disabled_send_tooltip_html();
                instance.setContent(parse_html(error_message));

                if (!error_message) {
                    blueslip.error("Compose send button incorrectly disabled.");
                    // We don't return but show normal tooltip to user.
                    instance.reference.classList.remove("disabled-message-send-controls");
                } else {
                    return undefined;
                }
            }

            if (user_settings.enter_sends) {
                instance.setContent(parse_html($("#send-enter-tooltip-template").html()));
            } else {
                instance.setContent(parse_html($("#send-ctrl-enter-tooltip-template").html()));
            }
            return undefined;
        },
    });

    tippy.delegate("body", {
        target: ".narrow_to_compose_recipients",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        content() {
            const narrow_filter = narrow_state.filter();
            let display_current_view;
            if (narrow_state.is_message_feed_visible()) {
                assert(narrow_filter !== undefined);
                if (narrow_filter.is_in_home()) {
                    display_current_view = $t({
                        defaultMessage: "Currently viewing your combined feed.",
                    });
                } else if (
                    _.isEqual(narrow_filter.sorted_term_types(), ["channel"]) &&
                    compose_state.get_message_type() === "stream" &&
                    narrow_filter.operands("channel")[0] === compose_state.stream_name()
                ) {
                    display_current_view = $t({
                        defaultMessage: "Currently viewing the entire channel.",
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
}

export function hide_compose_control_button_tooltips($row: JQuery): void {
    $row.find(
        ".compose_control_button[data-tooltip-template-id], .compose_control_button[data-tippy-content], .compose_control_button_container",
    ).each(function (this: tippy.ReferenceElement) {
        this._tippy?.hide();
    });
}
