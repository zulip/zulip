import $ from "jquery";
import _ from "lodash";
import tippy, {delegate} from "tippy.js";

import render_message_inline_image_tooltip from "../templates/message_inline_image_tooltip.hbs";
import render_narrow_to_compose_recipients_tooltip from "../templates/narrow_to_compose_recipients_tooltip.hbs";

import * as common from "./common";
import * as compose_state from "./compose_state";
import {$t} from "./i18n";
import * as message_lists from "./message_lists";
import * as narrow_state from "./narrow_state";
import * as popover_menus from "./popover_menus";
import * as reactions from "./reactions";
import * as recent_topics_util from "./recent_topics_util";
import * as rows from "./rows";
import * as timerender from "./timerender";
import {parse_html} from "./ui_util";

// For tooltips without data-tippy-content, we use the HTML content of
// a <template> whose id is given by data-tooltip-template-id.
function get_tooltip_content(reference) {
    if ("tooltipTemplateId" in reference.dataset) {
        const template = document.querySelector(
            `template#${CSS.escape(reference.dataset.tooltipTemplateId)}`,
        );
        return template.content.cloneNode(true);
    }
    return "";
}

// Defining observer outside ensures that at max only one observer is active at all times.
let observer;
function hide_tooltip_if_reference_removed(
    target_node,
    config,
    instance,
    nodes_to_check_for_removal,
) {
    // Use MutationObserver to check for removal of nodes on which tooltips
    // are still active.
    if (!target_node) {
        // The tooltip reference was removed from DOM before we reached here.
        // In that case, we simply hide the tooltip.
        // We have to be smart about hiding the instance, so we hide it as soon
        // as it is displayed.
        setTimeout(instance.hide, 0);
        return;
    }
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
}

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

    // To add a text tooltip, override this by setting data-tippy-content.
    // To add an HTML tooltip, set data-tooltip-template-id to the id of a <template>.
    // Or, override this with a function returning string (text) or DocumentFragment (HTML).
    content: get_tooltip_content,
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
            const $elem = $(instance.reference);
            if (!instance.reference.classList.contains("reaction_button")) {
                const local_id = $elem.attr("data-reaction-id");
                const message_id = rows.get_message_id(instance.reference);
                const title = reactions.get_reaction_title_data(message_id, local_id);
                instance.setContent(title);
            }

            const config = {attributes: false, childList: true, subtree: true};
            const target = $elem.parents(".message_table.focused_table").get(0);
            const nodes_to_check_for_removal = [
                $elem.parents(".recipient_row").get(0),
                $elem.parents(".message_reactions").get(0),
                $elem.get(0),
            ];
            hide_tooltip_if_reference_removed(target, config, instance, nodes_to_check_for_removal);
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
            const $elem = $(instance.reference);
            let content = $elem.attr("data-tippy-content");
            if (content === undefined) {
                // Tippy cannot get the content for message edit button
                // as it is dynamically inserted based on editability.
                // So, we have to manually get the i element to get the
                // content from it.
                //
                // TODO: Change the template structure so logic is unnecessary.
                const $edit_button = $elem.find("i.edit_content_button");
                content = $edit_button.attr("data-tippy-content");
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
            const $time_elem = $(instance.reference);
            const $row = $time_elem.closest(".message_row");
            const message = message_lists.current.get(rows.id($row));
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
            ".code_external_link",
        ],
        appendTo: () => document.body,
    });

    delegate("body", {
        target: ".rendered_markdown time",
        content: timerender.get_markdown_time_tooltip,
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: "#stream-specific-notify-table .unmute_stream",
        appendTo: () => document.body,
    });

    delegate("body", {
        target: [
            ".rendered_markdown .copy_codeblock",
            "#compose_top_right [data-tippy-content]",
            "#compose_top_right [data-tooltip-template-id]",
        ],
        appendTo: () => document.body,
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: ".narrow_to_compose_recipients",
        appendTo: () => document.body,
        content() {
            const narrow_filter = narrow_state.filter();
            let display_current_view;
            if (!recent_topics_util.is_visible()) {
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
                    _.isEqual(narrow_filter.sorted_term_types(), ["is-private"]) &&
                    compose_state.get_message_type() === "private"
                ) {
                    display_current_view = $t({
                        defaultMessage: "Currently viewing all private messages.",
                    });
                }
            }

            const shortcut_html = (common.has_mac_keyboard() ? "⌘" : "Ctrl") + " + .";
            return parse_html(
                render_narrow_to_compose_recipients_tooltip({shortcut_html, display_current_view}),
            );
        },
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

    delegate("body", {
        target: ".message_inline_image > a > img",
        appendTo: () => document.body,
        // Add a short delay so the user can mouseover several inline images without
        // tooltips showing and hiding rapidly
        delay: [300, 20],
        onShow(instance) {
            // Some message_inline_images aren't actually images with a title,
            // for example youtube videos, so we default to the actual href
            const title =
                $(instance.reference).parent().attr("aria-label") ||
                $(instance.reference).parent().attr("href");
            instance.setContent(parse_html(render_message_inline_image_tooltip({title})));

            const target_node = $(instance.reference)
                .parents(".message_table.focused_table")
                .get(0);
            const config = {attributes: false, childList: true, subtree: false};
            const nodes_to_check_for_removal = [
                $(instance.reference).parents(".message_inline_image").get(0),
            ];
            hide_tooltip_if_reference_removed(
                target_node,
                config,
                instance,
                nodes_to_check_for_removal,
            );
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        target: ".image-info-wrapper > .image-description > .title",
        appendTo: () => document.body,
        onShow(instance) {
            const title = $(instance.reference).attr("aria-label");
            const filename = $(instance.reference).prop("data-filename");
            const $markup = $("<span>").text(title);
            if (title !== filename) {
                // If the image title is the same as the filename, there's no reason
                // to show this next line.
                const second_line = $t({defaultMessage: "File name: {filename}"}, {filename});
                $markup.append($("<br>"), $("<span>").text(second_line));
            }
            instance.setContent($markup[0]);
        },
        onHidden(instance) {
            instance.destroy();
        },
    });

    delegate("body", {
        // Configure tooltips for the stream_sorter_toggle buttons.

        // TODO: Ideally, we'd extend this to be a common mechanism for
        // tab switchers, with the strings living in a more normal configuration
        // location.
        target: ".stream_sorter_toggle .ind-tab [data-tippy-content]",

        // Adjust their placement to `bottom`.
        placement: "bottom",

        // Avoid inheriting `position: relative` CSS on the stream sorter widget.
        appendTo: () => document.body,
    });

    delegate("body", {
        // This tooltip appears on the "Summary" checkboxes in
        // settings > custom profile fields, when at the limit of 2
        // fields with display_in_profile_summary enabled.
        target: [
            "#profile-field-settings .display_in_profile_summary_tooltip",
            "#edit-custom-profile-field-form-modal .display_in_profile_summary_tooltip",
            "#add-new-custom-profile-field-form .display_in_profile_summary_tooltip",
        ],
        content: $t({
            defaultMessage: "Only 2 custom profile fields can be displayed in the profile summary.",
        }),
        appendTo: () => document.body,
        onTrigger(instance) {
            // Sometimes just removing class is not enough to destroy/remove tooltip, especially in
            // "Add a new custom profile field" form, so here we are manually calling `destroy()`.
            if (!instance.reference.classList.contains("display_in_profile_summary_tooltip")) {
                instance.destroy();
            }
        },
    });

    delegate("body", {
        target: "#toggle_private_messages_section_icon",
        onShow(instance) {
            if ($("#toggle_private_messages_section_icon").hasClass("fa-caret-down")) {
                instance.setContent(
                    $t({
                        defaultMessage: "Collapse private messages",
                    }),
                );
            } else {
                instance.setContent($t({defaultMessage: "Expand private messages"}));
            }
        },
        appendTo: () => document.body,
    });

    delegate("body", {
        target: "#show_all_private_messages",
        placement: "bottom",
        onShow(instance) {
            instance.setContent(
                $t({
                    defaultMessage: "All private messages (P)",
                }),
            );
        },
        appendTo: () => document.body,
    });
}
