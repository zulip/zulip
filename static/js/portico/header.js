import $ from "jquery";

$(() => {
    $(".portico-header li.logout").on("click", () => {
        $("#logout_form").trigger("submit");
        return false;
    });

    const is_touchscreen = window.matchMedia("(hover: none)").matches;

    $("body").on("click", (e) => {
        const $this = $(e.target);
        const dropdown_is_shown = $this.closest("ul .dropdown").hasClass("show");
        const dropdown_label_was_clicked = $this.closest(".dropdown .dropdown-label").length > 0;
        const logged_in_pill_was_clicked = $this.closest(".dropdown .dropdown-pill").length > 0;
        const clicked_outside_dropdown_content =
            !$this.is(".dropdown ul") && $this.closest(".dropdown ul").length === 0;

        if (dropdown_label_was_clicked && !dropdown_is_shown && is_touchscreen) {
            $this.closest("ul .dropdown").addClass("show");
        } else if (logged_in_pill_was_clicked && !dropdown_is_shown) {
            $this.closest("ul .dropdown").addClass("show");
        } else if (clicked_outside_dropdown_content) {
            $this.closest("ul .dropdown").removeClass("show");
        }
    });

    $(".nav-dropdown").on("mouseover", (e) => {
        const $this = $(e.target);
        const dropdown_is_shown = $this.closest("ul .dropdown").hasClass("show");

        if (!dropdown_is_shown && !is_touchscreen) {
            $this.closest("ul .dropdown").addClass("show");
        }
    });

    $(".nav-dropdown").on("mouseout", (e) => {
        const $this = $(e.target);
        const dropdown_is_shown = $this.closest("ul .dropdown").hasClass("show");

        if (dropdown_is_shown && !is_touchscreen) {
            $this.closest("ul .dropdown").removeClass("show");
        }
    });
});
