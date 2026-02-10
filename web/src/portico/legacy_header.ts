import $ from "jquery";

/* Used by pages that load the legacy navbar,
   templates/zerver/portico-header.html */

$(".portico-header li.logout").on("click", () => {
    $("#logout_form").trigger("submit");
    return false;
});

$(".portico-header .portico-header-dropdown").on("click", (e) => {
    const $user_dropdown = $(e.target).closest(".portico-header-dropdown");
    const dropdown_is_shown = $user_dropdown.hasClass("show");

    if (!dropdown_is_shown) {
        $user_dropdown.addClass("show");
    } else if (dropdown_is_shown) {
        $user_dropdown.removeClass("show");
    }
});
