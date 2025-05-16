import $ from "jquery";

$("body").on("input", ".input-element", function (this: HTMLInputElement, _e: JQuery.Event) {
    const $input_clear_button = $(this).next(".input-clear-button");
    if (this.value.length === 0) {
        $input_clear_button.addClass("hide");
        $(this).removeClass("input-active");
    } else {
        $input_clear_button.removeClass("hide");
        $(this).addClass("input-active");
    }
});

$("body").on("click", ".input-clear-button", function (this: HTMLElement, _e: JQuery.Event) {
    const $input = $(this).prev(".input-element");
    $input.trigger("focus").val("").trigger("input");
});
