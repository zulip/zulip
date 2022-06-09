import $ from "jquery";

$(() => {
    $(".portico-header li.logout").on("click", () => {
        $("#logout_form").trigger("submit");
        return false;
    });

    $(".dropdown").on("click", (e) => {
        const $this = $(e.target);
        const dropdown_is_shown = $this.closest(".dropdown").hasClass("show");

        if (!dropdown_is_shown) {
            $this.closest(".dropdown").addClass("show");
        } else if (dropdown_is_shown) {
            $this.closest(".dropdown").removeClass("show");
        }
    });

    $(".nav-dropdown").on("mouseover", (e) => {
        const $this = $(e.target);
        // We switch to a vertical sidebar menu at width <= 1024px
        const in_vertical_orientation = window.matchMedia("(max-width: 1024px)").matches;
        // We only support mouseover events if we are in a horizontal
        // orientation (width > 1024px) and if the primary input mechanism
        // can hover over elements.
        const hover_supported = window.matchMedia("(hover: hover)").matches;
        const dropdown_is_shown = $this.closest("ul .dropdown").hasClass("show");

        if (!dropdown_is_shown && !in_vertical_orientation && hover_supported) {
            $this.closest("ul .dropdown").addClass("show");
        }
    });

    $(".nav-dropdown").on("mouseout", (e) => {
        const $this = $(e.target);
        // We switch to a vertical sidebar menu at width <= 1024px
        const in_vertical_orientation = window.matchMedia("(max-width: 1024px)").matches;
        // We only support mouseout events if we are in a horizontal
        // orientation (width > 1024px) and if the primary input mechanism
        // can hover over elements.
        const hover_supported = window.matchMedia("(hover: hover)").matches;
        const dropdown_is_shown = $this.closest("ul .dropdown").hasClass("show");

        if (dropdown_is_shown && !in_vertical_orientation && hover_supported) {
            $this.closest("ul .dropdown").removeClass("show");
        }
    });

    $("body").on("click", ".hamburger-portico, .cross-portico", (e) => {
        // Having a class which only works on mobile widths avoids it from still working when user resizes the window.
        $(".portico-header .top-links .portico_nav_dropdown").toggleClass("show_mobile");
        $(".portico-header .top-links .cross-portico").toggleClass("show_mobile");
        $(".portico-header .top-links .hamburger-portico").toggleClass("hide_mobile");

        e.preventDefault();
        e.stopPropagation();
    });
});
