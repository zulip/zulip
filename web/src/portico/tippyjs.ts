import $ from "jquery";
import * as tippy from "tippy.js";

const LONG_HOVER_DELAY: [number, number] = [750, 20];

function initialize(): void {
    tippy.default("[data-tippy-content]", {
        // Same defaults as set in web app tippyjs module.
        maxWidth: 300,
        delay: [100, 20],
        touch: ["hold", 750],
        // Different default from web app tippyjs module.
        animation: true,
        placement: "bottom",
    });

    tippy.default(".organization-name-delayed-tooltip", {
        maxWidth: 300,
        delay: LONG_HOVER_DELAY,
        touch: ["hold", 750],
        animation: true,
        placement: "bottom",
        onShow(instance) {
            const content = $(instance.reference).text();
            instance.setContent(content);
        },
    });
}

$(() => {
    initialize();
});
