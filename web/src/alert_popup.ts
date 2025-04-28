import $ from "jquery";

// this will hide the alerts that you click "x" on.
$("body").on("click", ".alert-box .exit", function () {
    const $alert = $(this).parent("div");
    $alert.addClass("fade-out");
    setTimeout(() => {
        $alert.removeClass("fade-out show");
    }, 300);
});

$(".blueslip-error-container").on("click", ".stackframe", function () {
    $(this).siblings(".code-context").toggle("fast");
});

$(".blueslip-error-container").on("click", ".exit", function () {
    const $stacktrace = $(this).closest(".stacktrace");
    $stacktrace.addClass("fade-out");
    setTimeout(() => {
        $stacktrace.removeClass("fade-out show");
    }, 300);
});
