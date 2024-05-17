import $ from "jquery";
import tippy from "tippy.js";

function initialize(): void {
    tippy("[data-tippy-content]", {
        // Same defaults as set in web app tippyjs module.
        maxWidth: 300,
        delay: [100, 20],
        touch: ["hold", 750],
        // Different default from web app tippyjs module.
        animation: true,
        placement: "bottom",
    });
}

$(() => {
    initialize();
});
