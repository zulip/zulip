import $ from "jquery";
import tippy, {delegate} from "tippy.js";

import * as reactions from "./reactions";
import * as rows from "./rows";

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
    placement: "auto",

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
    delegate("body", {
        // Add elements here which are not displayed on
        // initial load but are displayed later through
        // some means.
        //
        // Make all html elements having this class
        // show tippy styled tooltip on hover.
        target: ".tippy-zulip-tooltip",
    });

    // message reaction tooltip showing who reacted.
    delegate("body", {
        target: ".message_reaction",
        placement: "bottom",
        onShow(instance) {
            const elem = $(instance.reference);
            const local_id = elem.attr("data-reaction-id");
            const message_id = rows.get_message_id(instance.reference);
            const title = reactions.get_reaction_title_data(message_id, local_id);
            instance.setContent(title);
        },
        // Insert directly into the `.message_reaction` element so
        // that when the reaction is hidden, tooltip hides as well.
        appendTo: (reference) => reference,
    });
}
