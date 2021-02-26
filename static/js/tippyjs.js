import tippy, {delegate, hideAll} from "tippy.js";
const render_mobile_message_buttons_popover_content = require("../templates/mobile_message_buttons_popover_content.hbs");

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

    // compose box popover shown on
    // mobile widths.
    delegate('body', {
        delay: 0,
        target: '.compose_mobile_button',
        placement: "top",
        onShow(instance) {
            instance.setContent(render_mobile_message_buttons_popover_content({
                is_in_private_narrow: narrow_state.narrowed_to_pms(),
            }));
            $(instance.popper).on('click', instance.hide);
        },
        appendTo: () => document.body,
        trigger: 'click',
        allowHTML: true,
        interactive: true,
        theme: "light-border",
        hideOnClick: true,
    });
}
