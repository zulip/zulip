import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_message_edit_notice_tooltip from "../templates/message_edit_notice_tooltip.hbs";
import render_message_inline_image_tooltip from "../templates/message_inline_image_tooltip.hbs";
import render_narrow_tooltip from "../templates/narrow_tooltip.hbs";

import * as compose_validate from "./compose_validate.ts";
import {$t} from "./i18n.ts";
import * as message_lists from "./message_lists.ts";
import * as popover_menus from "./popover_menus.ts";
import * as reactions from "./reactions.ts";
import * as rows from "./rows.ts";
import {message_edit_history_visibility_policy_values} from "./settings_config.ts";
import {realm} from "./state_data.ts";
import * as timerender from "./timerender.ts";
import {
    INTERACTIVE_HOVER_DELAY,
    LONG_HOVER_DELAY,
    topic_visibility_policy_tooltip_props,
} from "./tippyjs.ts";
import {parse_html} from "./ui_util.ts";

type Config = {
    attributes: boolean;
    childList: boolean;
    subtree: boolean;
};

// We need to store all message list instances together to destroy them in case of re-rendering.
const message_list_tippy_instances = new Set<tippy.Instance>();

// This keeps track of all the instances created and destroyed.
const store_message_list_instances_plugin = {
    fn() {
        return {
            onCreate(instance: tippy.Instance) {
                message_list_tippy_instances.add(instance);
            },
            onDestroy(instance: tippy.Instance) {
                // To make sure the `message_list_tippy_instances` contains only instances
                // that are present in the DOM, we need to delete instances that are destroyed
                message_list_tippy_instances.delete(instance);
            },
        };
    },
};

function message_list_tooltip(target: string, props: Partial<tippy.Props> = {}): void {
    const {onShow, ...other_props} = props;
    tippy.delegate("body", {
        target,
        appendTo: () => document.body,
        plugins: [store_message_list_instances_plugin],
        onShow(instance) {
            if (message_lists.current === undefined) {
                // Since tooltips is called with a delay, it is possible that the
                // message feed is not visible when the tooltip is shown.
                return false;
            }

            if (onShow !== undefined && onShow(instance) === false) {
                // Only return false if `onShow` returns false. We don't want to hide
                // tooltip if `onShow` returns `undefined`.
                return false;
            }

            return undefined;
        },
        ...other_props,
    });
}

// Defining observer outside ensures that at max only one observer is active at all times.
let observer;
function hide_tooltip_if_reference_removed(
    target_node: HTMLElement,
    config: Config,
    instance: tippy.Instance,
    nodes_to_check_for_removal: tippy.ReferenceElement[],
): void {
    // Use MutationObserver to check for removal of nodes on which tooltips
    // are still active.
    if (!target_node) {
        // The tooltip reference was removed from DOM before we reached here.
        // In that case, we simply hide the tooltip.
        // We have to be smart about hiding the instance, so we hide it as soon
        // as it is displayed.
        setTimeout(() => {
            popover_menus.hide_current_popover_if_visible(instance);
        }, 0);
        return;
    }
    const callback = function (mutationsList: MutationRecord[]): void {
        for (const mutation of mutationsList) {
            for (const node of nodes_to_check_for_removal) {
                // Hide instance if reference's class changes.
                if (mutation.type === "attributes" && mutation.attributeName === "class") {
                    popover_menus.hide_current_popover_if_visible(instance);
                }
                // Hide instance if reference is in the removed node list.
                if (Array.prototype.includes.call(mutation.removedNodes, node)) {
                    popover_menus.hide_current_popover_if_visible(instance);
                }
            }
        }
    };
    observer = new MutationObserver(callback);
    observer.observe(target_node, config);
}

// To prevent the appearance of tooltips whose reference is hidden or removed from the
// DOM during re-rendering, we need to destroy all the message list present instances,
// and then initialize triggers of the tooltips again after re-rendering.
export function destroy_all_message_list_tooltips(): void {
    for (const instance of message_list_tippy_instances) {
        if (instance.reference === document.body) {
            continue;
        }
        instance.destroy();
    }
    message_list_tippy_instances.clear();
}

function get_time_string(timestamp: number): string {
    const last_modified_time = new Date(timestamp * 1000);
    let date = timerender.render_date(last_modified_time).textContent;
    // If the date is today or yesterday, we don't want to show the date as capitalized.
    // Thus, we need to check if the date string contains a digit or not using regex,
    // since any other date except today/yesterday will contain a digit.
    if (date && !/\d/.test(date)) {
        date = date.toLowerCase();
    }
    return $t(
        {defaultMessage: "{date} at {time}"},
        {
            date,
            time: timerender.stringify_time(last_modified_time),
        },
    );
}

export function initialize(): void {
    message_list_tooltip(".tippy-narrow-tooltip", {
        delay: LONG_HOVER_DELAY,
        onCreate(instance) {
            instance.setContent(
                parse_html(render_narrow_tooltip({content: instance.props.content})),
            );
        },
    });

    // message reaction tooltip showing who reacted.
    let observer: MutationObserver | undefined;
    message_list_tooltip(".message_reaction", {
        delay: INTERACTIVE_HOVER_DELAY,
        placement: "bottom",
        onShow(instance) {
            if (!document.body.contains(instance.reference)) {
                // It is possible for reaction to be removed before `onShow` is triggered,
                // so, we check if the element exists before proceeding.
                return false;
            }
            const $elem = $(instance.reference);
            const local_id = $elem.attr("data-reaction-id");
            assert(local_id !== undefined);
            assert(instance.reference instanceof HTMLElement);
            const message_id = rows.get_message_id(instance.reference);
            const title = reactions.get_reaction_title_data(message_id, local_id);
            instance.setContent(title);

            const config = {attributes: false, childList: true, subtree: true};
            const target = $elem.parents(".message-list.focused-message-list").get(0);
            assert(target !== undefined);
            const nodes_to_check_for_removal = [
                $elem.parents(".recipient_row").get(0)!,
                $elem.parents(".message_reactions").get(0)!,
                $elem.get(0)!,
            ];
            hide_tooltip_if_reference_removed(target, config, instance, nodes_to_check_for_removal);
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
            if (observer) {
                observer.disconnect();
            }
        },
    });

    message_list_tooltip(".message_reactions .reaction_button", {
        delay: LONG_HOVER_DELAY,
        placement: "bottom",
        onShow(instance) {
            if (!document.body.contains(instance.reference)) {
                // It is possible for the single reaction necessary for
                // displaying the reaction button to be removed before
                // `onShow` is triggered, so we check if the element
                // exists before proceeding.
                return false;
            }
            const $elem = $(instance.reference);

            if ($elem.hasClass("active-emoji-picker-reference")) {
                // Don't show the tooltip when the emoji picker is open
                return false;
            }

            const config = {attributes: false, childList: true, subtree: true};
            const target = $elem.parents(".message-list.focused-message-list").get(0);
            assert(target !== undefined);
            const nodes_to_check_for_removal = [
                $elem.parents(".recipient_row").get(0)!,
                $elem.parents(".message_reactions").get(0)!,
                $elem.get(0)!,
            ];
            hide_tooltip_if_reference_removed(target, config, instance, nodes_to_check_for_removal);
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".message_control_button", {
        delay: LONG_HOVER_DELAY,
        onShow(instance) {
            // Handle dynamic "starred messages" and "edit" widgets.
            const $elem = $(instance.reference);
            const tippy_content = $elem.attr("data-tippy-content");
            if (tippy_content !== undefined) {
                instance.setContent(tippy_content);
            } else {
                const template_id = $elem.attr("data-tooltip-template-id");
                if (template_id === undefined) {
                    return false;
                }
                const $template = $(`#${CSS.escape(template_id)}`);
                instance.setContent(parse_html($template.html()));
            }
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".slow-send-spinner", {
        onShow(instance) {
            const $elem = $(instance.reference);

            // We need to check for removal of local class from message_row since
            // .slow-send-spinner is not removed (hidden) from DOM when message is sent.
            const target = $elem.parents(".message_row").get(0);
            assert(target !== undefined);
            const config = {attributes: true, childList: false, subtree: false};
            const nodes_to_check_for_removal = [$elem.get(0)!];
            hide_tooltip_if_reference_removed(target, config, instance, nodes_to_check_for_removal);
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".message-list .message-time", {
        onShow(instance) {
            const $time_elem = $(instance.reference);
            const $row = $time_elem.closest(".message_row");
            assert(message_lists.current !== undefined);
            const message = message_lists.current.get(rows.id($row))!;
            // Don't show time tooltip for locally echoed message.
            if (message.locally_echoed) {
                return false;
            }
            const time = new Date(message.timestamp * 1000);
            instance.setContent(timerender.get_full_datetime_clarification(time));
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".disabled-message-edit-save", {
        onShow(instance) {
            const $elem = $(instance.reference);
            const $row = $elem.closest(".message_row");
            assert($row !== undefined);
            instance.setContent(compose_validate.get_disabled_save_tooltip($row));
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".recipient_row_date > span", {
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(
        ".rendered_markdown .copy_codeblock, .rendered_markdown .code_external_link",
        {
            onHidden(instance) {
                instance.destroy();
            },
        },
    );

    message_list_tooltip(
        "#message_feed_container .change_visibility_policy > .recipient-bar-control-icon",
        {
            ...topic_visibility_policy_tooltip_props,
        },
    );

    message_list_tooltip("#message_feed_container .recipient-bar-control-icon", {
        delay: LONG_HOVER_DELAY,
        onShow(instance) {
            const $reference = $(instance.reference);
            if ($reference.hasClass("loading-resolve-topic-state")) {
                // Don't show tooltip when the loading indicator is being
                // displayed while resolving/unresolving a topic.
                return false;
            }
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".rendered_markdown time", {
        // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
        content: timerender.get_markdown_time_tooltip as tippy.Content,
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".message_inline_image > a > img", {
        // Add a short delay so the user can mouseover several inline images without
        // tooltips showing and hiding rapidly
        delay: [300, 20],
        onShow(instance) {
            // Some message_inline_images aren't actually images with a title,
            // for example youtube videos, so we default to the actual href
            const title =
                $(instance.reference).parent().attr("aria-label") ??
                $(instance.reference).parent().attr("href");
            instance.setContent(parse_html(render_message_inline_image_tooltip({title})));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".view_user_card_tooltip", {
        delay: LONG_HOVER_DELAY,
        onShow(instance) {
            const is_bot = $(instance.reference).attr("data-is-bot") === "true";
            if (is_bot) {
                instance.setContent(parse_html($("#view-bot-card-tooltip-template").html()));
            } else {
                instance.setContent(parse_html($("#view-user-card-tooltip-template").html()));
            }
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".message_edit_notice, .edit-notifications", {
        trigger: "mouseenter",
        delay: LONG_HOVER_DELAY,
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
        onShow(instance) {
            const $elem = $(instance.reference);
            const message_id = Number($elem.closest(".message_row").attr("data-message-id"));

            assert(message_lists.current !== undefined);
            const message_container = message_lists.current.view.message_containers.get(message_id);
            assert(message_container !== undefined);
            // If there is no indicator that the message has been modified (saving,
            // edited, moved), then we don't show the message edit notice tooltip.
            if (!message_container.modified) {
                return false;
            }
            let edited_time_string = "";
            let moved_time_string = "";
            if (message_container.edited) {
                // We know the message has been edited, so we either have a timestamp
                // from the server or from a local edit.
                assert(message_container.last_edit_timestamp !== undefined);
                edited_time_string = get_time_string(message_container.last_edit_timestamp);
            }
            if (message_container.moved) {
                // We know the message has been moved, so we have a timestamp from
                // the server.
                assert(message_container.last_moved_timestamp !== undefined);
                moved_time_string = get_time_string(message_container.last_moved_timestamp);
            }
            const edit_history_access =
                realm.realm_message_edit_history_visibility_policy ===
                message_edit_history_visibility_policy_values.always.code;
            const message_moved_and_move_history_access =
                realm.realm_message_edit_history_visibility_policy ===
                    message_edit_history_visibility_policy_values.moves_only.code &&
                message_container.moved;
            instance.setContent(
                parse_html(
                    render_message_edit_notice_tooltip({
                        moved: message_container.moved,
                        edited: message_container.edited,
                        edited_time_string,
                        moved_time_string,
                        edit_history_access,
                        message_moved_and_move_history_access,
                    }),
                ),
            );
            return undefined;
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    message_list_tooltip(".message_expander, .message_condenser", {
        delay: LONG_HOVER_DELAY,
        onHidden(instance) {
            instance.destroy();
        },
    });
}
