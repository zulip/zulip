import $ from "jquery";

// this will hide the alerts that you click "x" on.
$("body").on("click", ".alert-box .exit", function () {
    const $alert = $(this).parent("div");
    $alert.addClass("fade-out");
    setTimeout(() => {
        $alert.removeClass("fade-out show");
    }, 300);
});
