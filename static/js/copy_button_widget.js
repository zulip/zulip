import ClipboardJS from "clipboard";
import $ from "jquery";
import tippy from "tippy.js";

import * as blueslip from "./blueslip";
import {$t} from "./i18n";

let timeout = null;

/*
    Have a look at `popovers.js` and `rendered_markdown.js`
    for an example on how to use this widget.
    Parameters that can be passed -

    element- The Jquery element that triggers the copy event.
    content- The text to be rendered as the tooltip.
    placement- Sets the tooltip placement having the text as `content`.
    on_show- Defines the function to trigger once tooltip is shown.
    on_hide- Defines the function to trigger once tooltip is hidden.
    text- Used to dynamically set a text as a ClipboardJS event.
    on_success- Function to trigger once text is successfully copied.
    on_error- Function to trigger once the clipboard event is failed.

*/

function render_tooltip(opts) {
    tippy(opts.element, {
        content: opts.content,
        placement: opts.placement,
    });
}

// Builds up the tooltip that should be rendered upon
// hovering the button.
function register_hover_tooltip(opts) {
    const tooltip = opts.element._tippy;

    $(opts.element).on("mouseenter", () => {
        // Stop the execution if the `Copied` tooltip
        // is still being shown.
        if (timeout) {
            return;
        }
        if (opts.on_show) {
            opts.on_show();
        }
        tooltip.setContent(opts.content);
    });

    // Default back the values if mouse leaves the copy button.
    $(opts.element).on("mouseleave", () => {
        clearTimeout(timeout);
        timeout = null;

        if (opts.on_hide) {
            opts.on_hide();
        }
    });
}

// Change the tooltip content to `Copied!`.
function clipboard_success_handler(element) {
    const tooltip = element._tippy;

    tooltip.setContent($t({defaultMessage: "Copied!"}));
    tooltip.show(300);

    // Display the tooltip for 2 seconds.
    timeout = setTimeout(() => {
        tooltip.hide(300);
        timeout = null;
    }, 2000);
}

// Builds up the object that is to be passed in ClipboardJS constructor.
function build_clipboard_events(opts) {
    const event = {};

    if (opts.text) {
        event.text = function (copy_event) {
            return opts.text(copy_event);
        };
    }

    return event;
}

export function show(opts) {
    const required_fields = [
        // These are the fields that must be passed in `opts`
        // parameter in order to initialize `copy_button_widget`.
        // Element here needs to be a Jquery object.
        "content",
        "element",
        "placement",
    ];

    // Reduce down the jquery object it's DOM element.
    opts.element = opts.element[0];

    for (const param of required_fields) {
        if (opts[param] === undefined) {
            blueslip.error("programmer omitted " + param);
        }
    }

    render_tooltip(opts);
    register_hover_tooltip(opts);

    // Initialize the ClipboardJS handlers.
    const copy_event = new ClipboardJS(opts.element, build_clipboard_events(opts));

    copy_event.on("success", (e) => {
        clipboard_success_handler(opts.element);
        if (opts.on_success) {
            opts.on_success(e);
        }
    });

    copy_event.on("error", (e) => {
        if (opts.on_error) {
            opts.on_error(e);
        }
    });
}
