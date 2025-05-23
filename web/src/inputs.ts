import $ from "jquery";

$("body").on("input", ".input-element", function (this: HTMLInputElement, _e: JQuery.Event) {
    if (this.value.length === 0) {
        $(this).removeClass("input-element-nonempty");
    } else {
        $(this).addClass("input-element-nonempty");
    }
});

$("body").on(
    "click",
    ".filter-input .input-button",
    function (this: HTMLElement, _e: JQuery.Event) {
        const $input = $(this).prev(".input-element");
        $input.val("").trigger("input");
        $input.trigger("blur");
    },
);
