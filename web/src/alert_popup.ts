import $ from "jquery";

// this will hide the alerts that you click "x" on.
$("body").on("click", ".alert-box .exit", function () {
    const $stack_trace = $(this).closest(".stacktrace");
    $stack_trace.addClass("fade-out");
    setTimeout(() => {
        $stack_trace.removeClass("fade-out show");
    }, 300);
});
