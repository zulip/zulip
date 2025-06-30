import $ from "jquery";
import * as tippy from "tippy.js";

import * as drafts from "./drafts.ts";
import {$t} from "./i18n.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as settings_data from "./settings_data.ts";
import * as starred_messages from "./starred_messages.ts";
import {
    EXTRA_LONG_HOVER_DELAY,
    LONG_HOVER_DELAY,
    get_tooltip_content,
    topic_visibility_policy_tooltip_props,
} from "./tippyjs.ts";
import * as unread from "./unread.ts";
import {user_settings} from "./user_settings.ts";

export function initialize(): void {
    tippy.delegate("body", {
        target: ".tippy-left-sidebar-tooltip",
        placement: "right",
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onShow(instance) {
            const $container = $(instance.popper).find(".views-tooltip-container");
            let display_count = 0;
            const sidebar_option = $container.attr("data-view-code");

            switch (sidebar_option) {
                case user_settings.web_home_view:
                    $container.find(".views-tooltip-home-view-note").removeClass("hide");
                    display_count = unread.get_counts().home_unread_messages;
                    $container.find(".views-message-count").text(
                        $t(
                            {
                                defaultMessage:
                                    "You have {display_count, plural, =0 {no unread messages} one {# unread message} other {# unread messages}}.",
                            },
                            {display_count},
                        ),
                    );
                    break;
                case "mentions":
                    display_count = unread.unread_mentions_counter.size;
                    $container.find(".views-message-count").text(
                        $t(
                            {
                                defaultMessage:
                                    "You have {display_count, plural, =0 {no unread mentions} one {# unread mention} other {# unread mentions}}.",
                            },
                            {display_count},
                        ),
                    );
                    break;
                case "starred_message":
                    display_count = starred_messages.get_count();
                    $container.find(".views-message-count").text(
                        $t(
                            {
                                defaultMessage:
                                    "You have {display_count, plural, =0 {no starred messages} one {# starred message} other {# starred messages}}.",
                            },
                            {display_count},
                        ),
                    );
                    break;
                case "drafts":
                    display_count = drafts.draft_model.getDraftCount();
                    $container.find(".views-message-count").text(
                        $t(
                            {
                                defaultMessage:
                                    "You have {display_count, plural, =0 {no drafts} one {# draft} other {# drafts}}.",
                            },
                            {display_count},
                        ),
                    );
                    break;
                case "scheduled_message":
                    display_count = scheduled_messages.get_count();
                    $container.find(".views-message-count").text(
                        $t(
                            {
                                defaultMessage:
                                    "You have {display_count, plural, =0 {no scheduled messages} one {# scheduled message} other {# scheduled messages}}.",
                            },
                            {display_count},
                        ),
                    );
                    break;
            }

            // Since the tooltip is attached to the anchor tag which doesn't
            // include width of the ellipsis icon, we need to offset the
            // tooltip so that the tooltip is displayed to right of the
            // ellipsis icon.
            if (instance.reference.classList.contains("left-sidebar-navigation-label-container")) {
                instance.setProps({
                    offset: [0, 40],
                });
            }
        },
        onHidden(instance) {
            instance.destroy();
        },
        popperOptions: {
            modifiers: [
                {
                    name: "flip",
                    options: {
                        fallbackPlacements: "bottom",
                    },
                },
            ],
        },
    });

    // Variant of .tippy-left-sidebar-tooltip configuration. Since
    // some elements don't have an always visible label, and
    // thus hovering them is a way to find out what they do, give
    // them the shorter LONG_HOVER_DELAY.
    tippy.delegate("body", {
        target: ".tippy-left-sidebar-tooltip-no-label-delay",
        placement: "right",
        delay: LONG_HOVER_DELAY,
        appendTo: () => document.body,
        popperOptions: {
            modifiers: [
                {
                    name: "flip",
                    options: {
                        fallbackPlacements: "bottom",
                    },
                },
            ],
        },
    });

    tippy.delegate("body", {
        target: ["#streams_header .streams-tooltip-target", "#filter_streams_tooltip"].join(","),
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: "#add_streams_tooltip",
        onShow(instance) {
            const can_create_streams =
                settings_data.user_can_create_private_streams() ||
                settings_data.user_can_create_public_streams() ||
                settings_data.user_can_create_web_public_streams();
            const tooltip_text = can_create_streams
                ? $t({defaultMessage: "Add channels"})
                : $t({defaultMessage: "Browse channels"});
            instance.setContent(tooltip_text);
        },
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: ".views-tooltip-target",
        onShow(instance) {
            if ($("#toggle-top-left-navigation-area-icon").hasClass("rotate-icon-down")) {
                instance.setContent(
                    $t({
                        defaultMessage: "Collapse views",
                    }),
                );
            } else {
                instance.setContent($t({defaultMessage: "Expand views"}));
            }
        },
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
    });

    tippy.delegate("body", {
        target: ".dm-tooltip-target",
        onShow(instance) {
            if ($(".direct-messages-container").hasClass("zoom-in")) {
                return false;
            }

            if ($("#toggle-direct-messages-section-icon").hasClass("rotate-icon-down")) {
                instance.setContent(
                    $t({
                        defaultMessage: "Collapse direct messages",
                    }),
                );
            } else {
                instance.setContent($t({defaultMessage: "Expand direct messages"}));
            }
            return undefined;
        },
        delay: EXTRA_LONG_HOVER_DELAY,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: ".header-main .column-left .left-sidebar-toggle-button",
        delay: LONG_HOVER_DELAY,
        placement: "bottom",
        appendTo: () => document.body,
        onShow(instance) {
            let template = "show-left-sidebar-tooltip-template";
            if ($("#left-sidebar-container").css("display") !== "none") {
                template = "hide-left-sidebar-tooltip-template";
            }
            $(instance.reference).attr("data-tooltip-template-id", template);
            instance.setContent(get_tooltip_content(instance.reference));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    tippy.delegate("body", {
        target: [
            "#inbox-view .recipient_bar_icon",
            "#left-sidebar-container .visibility-policy-icon",
        ].join(","),
        ...topic_visibility_policy_tooltip_props,
    });
}
