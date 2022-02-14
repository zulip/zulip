import $ from "jquery";
import tippy, {delegate} from "tippy.js";

import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as popover_menus from "./popover_menus";
import * as reactions from "./reactions";
import * as rows from "./rows";
import * as timerender from "./timerender";

// We override the defaults set by tippy library here,
// so make sure to check this too after checking tippyjs
// documentation for default properties.
tippy.setDefaultProps({
    // We don't want tooltips
    // to take more space than
    // mobile widths ever.
    maxWidth: 300,

    // Some delay to showing / hiding the tooltip makes
    // it look less forced and more natural.
    delay: [100, 20],
    placement: "top",

    // disable animations to make the
    // tooltips feel snappy
    animation: false,

    // Show tooltips on long press on touch based
    // devices.
    touch: ["hold", 750],

    // This has the side effect of some properties of parent applying to
    // tooltips.
    appendTo: "parent",

    // html content is not supported by default
    // enable it by passing data-tippy-allowHtml="true"
    // in the tag or a parameter.
});

export function initialize() {
    // Our default tooltip configuration. For this, one simply needs to:
    // * Set `class="tippy-zulip-tooltip"` on an element for enable this.
    // * Set `data-tippy-content="{{t 'Tooltip content' }}"`, often
    //   replacing a `title` attribute on an element that had both.
    // * Set placement; we typically use `data-tippy-placement="top"`.
    delegate("body", {
        target: ".tippy-zulip-tooltip",
    });

    // The below definitions are for specific tooltips that require
    // custom JavaScript code or configuration.  Note that since the
    // below specify the target directly, elements using those should
    // not have the tippy-zulip-tooltip class.

    // message reaction tooltip showing who reacted.
    let observer;
    delegate("body", {
        target: ".message_reaction, .message_reactions .reaction_button",
        placement: "bottom",
        onShow(instance) {
            const elem = $(instance.reference);
            if (!instance.reference.classList.contains("reaction_button")) {
                const local_id = elem.attr("data-reaction-id");
                const message_id = rows.get_message_id(instance.reference);
                const title = reactions.get_reaction_title_data(message_id, local_id);
                instance.setContent(title);
            }

            // Use MutationObserver to check for removal of nodes on which tooltips
            // are still active.
            // We target the message table and check for removal of it, it's children
            // and the reactions individually down in the subtree.
            const target_node = elem.parents(".message_table.focused_table").get(0);
            if (!target_node) {
                // The `reaction` was removed from DOM before we reached here.
                // In that case, we simply hide the tooltip.
                // We have to be smart about hiding the instance, so we hide it as soon
                // as it is displayed.
                setTimeout(instance.hide, 0);
                return;
            }

            const nodes_to_check_for_removal = [
                elem.parents(".recipient_row").get(0),
                elem.parents(".message_reactions").get(0),
                elem.get(0),
            ];
            const config = {attributes: false, childList: true, subtree: true};

            const callback = function (mutationsList) {
                for (const mutation of mutationsList) {
                    for (const node of nodes_to_check_for_removal) {
                        // Hide instance if reference is in the removed node list.
                        if (Array.prototype.includes.call(mutation.removedNodes, node)) {
                            instance.hide();
                        }
                    }
                }
            };
            observer = new MutationObserver(callback);
            observer.observe(target_node, config);
        },
        onHidden(instance) {
            instance.destroy();
            if (observer) {
                observer.disconnect();
            }
        },
        appendTo: () => document.body,
    });

    delegate("body", {
        target: ".compose_control_button",
        // Add some additional delay when they open
        // so that regular users don't have to see
        // them unless they want to.
        delay: [300, 20],
        // This ensures that the upload files tooltip
        // doesn't hide behind the left sidebar.
        appendTo: () => document.body,
    });

    delegate("body", {
        target: ".message_control_button",
        // This ensures that the tooltip doesn't
        // hide by the selected message blue border.
        appendTo: () => document.body,
        // Add some additional delay when they open
        // so that regular users don't have to see
        // them unless they want to.
        delay: [300, 20],
        onShow(instance) {
            // Handle dynamic "starred messages" and "edit" widgets.
            const elem = $(instance.reference);
            let content = elem.attr("data-tippy-content");
            if (content === undefined) {
                // Tippy cannot get the content for message edit button
                // as it is dynamically inserted based on editability.
                // So, we have to manually get the i element to get the
                // content from it.
                //
                // TODO: Change the template structure so logic is unnecessary.
                const edit_button = elem.find("i.edit_content_button");
                content = edit_button.attr("data-tippy-content");
            }

            instance.setContent(content);
            return true;
        },
    });

    $("body").on("blur", ".message_control_button", (e) => {
        // Remove tooltip when user is trying to tab through all the icons.
        // If user tabs slowly, tooltips are displayed otherwise they are
        // destroyed before they can be displayed.
        e.currentTarget._tippy.destroy();
    });

    delegate("body", {
        target: ".message_table .message_time",
        appendTo: () => document.body,
        onShow(instance) {
            const time_elem = $(instance.reference);
            const row = time_elem.closest(".message_row");
            const message = message_lists.current.get(rows.id(row));
            const time = new Date(message.timestamp * 1000);
            instance.setContent(timerender.get_full_datetime(time));
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: ".recipient_row_date > span",
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    // In case of recipient bar icons, following change
    // ensures that tooltip doesn't hide behind the message
    // box or it is not limited by the parent container.
    delegate("body", {
        target: [
            ".recipient_bar_icon",
            ".sidebar-title",
            "#user_filter_icon",
            "#scroll-to-bottom-button-clickable-area",
        ],
        appendTo: () => document.body,
    });

    delegate("body", {
        target: [
            ".rendered_markdown time",
            ".rendered_markdown .copy_codeblock",
            "#compose_top_right [data-tippy-content]",
        ],
        allowHTML: true,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: [".enter_sends_true", ".enter_sends_false"],
        content: $t({defaultMessage: "Change send shortcut"}),
        onShow() {
            // Don't show tooltip if the popover is displayed.
            if (popover_menus.compose_enter_sends_popover_displayed) {
                return false;
            }
            return true;
        },
        appendTo: () => document.body,
    });
}
