import {$} from "jquery";

$("body").on(
    "click",
    ".filter-input .input-close-filter-button",
    function (this: HTMLElement, _e: JQuery.Event) {
        const $input = $(this).prev(".input-element");
        if ($input.attr("contenteditable") === "true") {
            $input.text("").trigger("input");
        } else {
            $input.val("").trigger("input");
        }
        $input.trigger("blur");
    },
);
