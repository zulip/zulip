import $ from "jquery";

$("body").on("input", ".input-element", function (this: HTMLInputElement, _e: JQuery.Event) {
    if (this.value.length === 0) {
        $(this).removeClass("input-element-active");
    } else {
        $(this).addClass("input-element-active");
    }
});

$("body").on(
    "click",
    ".filter-input .input-action-button",
    function (this: HTMLElement, _e: JQuery.Event) {
        const $input = $(this).prev(".input-element");
        $input.val("").trigger("input");
        $input.trigger("blur");
    },
);
