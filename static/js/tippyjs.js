import tippy, {delegate, hideAll} from "tippy.js";

tippy.setDefaultProps({
    // We don't want tooltips
    // to take more space than
    // mobile widths ever.
    maxWidth: 300,
    // show, hide
    delay: [0, 20],
    placement: "auto",
    animation: "scale",
    inertia: true,
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
}
