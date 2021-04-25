import $ from "jquery";

// this will hide the alerts that you click "x" on.
$("body").on("click", ".alert-box > div .exit", function () {
    const $alert = $(this).closest(".alert-box > div");
    $alert.addClass("fade-out");
    setTimeout(() => {
        $alert.removeClass("fade-out show");
    }, 300);
});

$(".alert-box").on("click", ".stackframe", function () {
    $(this).siblings(".code-context").toggle("fast");
});
