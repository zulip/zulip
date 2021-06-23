import $ from "jquery";

$(() => {
    $(".portico-header li.logout").on("click", () => {
        $("#logout_form").trigger("submit");
        return false;
    });

    $("body").on("click", (e) => {
        const $this = $(e.target);

        if (
            $this.closest(".dropdown .dropdown-label").length > 0 &&
            !$this.closest("ul .dropdown").hasClass("show") &&
            window.matchMedia("(max-width: 686px)").matches
        ) {
            $this.closest("ul .dropdown").addClass("show");
        } else if (
            $this.closest(".dropdown .dropdown-pill").length > 0 &&
            !$this.closest("ul .dropdown").hasClass("show")
        ) {
            $this.closest("ul .dropdown").addClass("show");
        } else if (!$this.is(".dropdown ul") && $this.closest(".dropdown ul").length === 0) {
            $this.closest("ul .dropdown").removeClass("show");
        }
    });

    $(".nav-dropdown").on("mouseover", (e) => {
        const $this = $(e.target);
        if (
            !$this.closest("ul .dropdown").hasClass("show") &&
            window.matchMedia("(min-width: 687px)").matches
        ) {
            $this.closest("ul .dropdown").addClass("show");
        }
    });

    $(".nav-dropdown").on("mouseout", (e) => {
        const $this = $(e.target);
        if (
            $this.closest("ul .dropdown").hasClass("show") &&
            window.matchMedia("(min-width: 687px)").matches
        ) {
            $this.closest("ul .dropdown").removeClass("show");
        }
    });
});
