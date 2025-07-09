import $ from "jquery";

// We use the `input` tag in the selector to avoid conflicts with the pill containing
// counterpart, which uses a `contenteditable` div instead of an input element.
$("body").on("input", "input.input-element", function (this: HTMLInputElement, _e: JQuery.Event) {
    if (this.value.length === 0) {
        $(this).removeClass("input-element-nonempty");
    } else {
        $(this).addClass("input-element-nonempty");
    }
});

$("body").on(
    "input change",
    ".has-input-pills .pill-container",
    function (this: HTMLInputElement, _e: JQuery.Event) {
        // We define another event handler for inputs with pill, similar to the one above.
        // However, due to the way inputs with pill use a contenteditable div instead of an
        // input element, we need to check the textContent of the pill container instead of
        // the value of an input element.
        // Here we need to listen to the `change` event in conjunction with the `input` event
        // to handle the addition or removal of input pills.
        const value = this.textContent?.trim() ?? "";
        if (value.length === 0) {
            $(this).removeClass("input-element-nonempty");
        } else {
            $(this).addClass("input-element-nonempty");
        }
    },
);

$("body").on(
    "click",
    ".filter-input .input-button",
    function (this: HTMLElement, _e: JQuery.Event) {
        const $input = $(this).prev(".input-element");
        $input.val("").trigger("input");
        $input.trigger("blur");
    },
);
