import $ from "jquery";

$(() => {
    function on_tab_menu_selection_change(
        event?: JQuery.ChangeEvent<HTMLElement> | JQuery.ClickEvent<HTMLElement>,
    ): void {
        // Pass event to open menu and if it is undefined, we close the menu.
        if (!event) {
            $("#top-menu-submenu-backdrop").css("height", "0px");
            return;
        }
        const el = event.target.parentElement.querySelector(".top-menu-submenu");
        if (el) {
            $("#top-menu-submenu-backdrop").css("height", Number(el.offsetHeight) + 16);
        } else {
            $("#top-menu-submenu-backdrop").css("height", 0);
        }
    }

    function on_top_menu_tab_unselect_click(): void {
        // Close the menu.
        $("#top-menu-tab-close").prop("checked", true);
        on_tab_menu_selection_change();
    }

    // In case user presses `back` with menu open.
    // See https://github.com/zulip/zulip/pull/24301#issuecomment-1418547337.
    if ($(".top-menu-tab-input:checked").length === 1) {
        const sub_menu_height = $(".top-menu-tab-input:checked ~ .top-menu-submenu").height() ?? 0;
        $("#top-menu-submenu-backdrop").css("height", sub_menu_height + 16);
    }

    // Close navbar if already open when user clicks outside the navbar.
    $("body").on("click", (e) => {
        const is_navbar_expanded = $(".top-menu-tab-input:checked").length === 1;
        const is_click_outside_navbar = $(".top-menu").find(e.target).length === 0;
        if (is_navbar_expanded && is_click_outside_navbar) {
            on_top_menu_tab_unselect_click();
        }
    });

    $(".logout_button").on("click", () => {
        $("#logout_form").trigger("submit");
    });

    $(".top-menu-tab-input").on("click", (e) => {
        on_tab_menu_selection_change(e);
    });

    $(".top-menu-tab-unselect").on("click", () => {
        on_top_menu_tab_unselect_click();
    });

    $("#top-menu-tab-close").on("change", () => {
        on_tab_menu_selection_change();
    });

    $("body").on("change", "top-menu-tab-input", (e) => {
        $("#top-menu-tab-close").prop("checked", true);
        on_tab_menu_selection_change(e);
    });

    // Helps make the keyboard navigation work.
    $("body").on("keydown", ".nav-menu-label, .top-menu-tab-label-unselect", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            e.stopPropagation();
            const labelID = $(e.currentTarget).attr("for");
            if (labelID === undefined) {
                throw new Error("Current target of this event must have for attribute defined.");
            }
            $(`#${CSS.escape(labelID)}`).trigger("click");
        }
    });

    $("body").on("click", ".top-menu-mobile", (e) => {
        if (e.target.open) {
            document.body.classList.add("_full-height-no-scroll");
        } else {
            document.body.classList.remove("_full-height-no-scroll");
        }
    });

    /* Used by navbar of non-corporate URLs. */
    $(".portico-header li.logout").on("click", () => {
        $("#logout_form").trigger("submit");
        return false;
    });

    $(".portico-header .dropdown").on("click", (e) => {
        const $user_dropdown = $(e.target).closest(".dropdown");
        const dropdown_is_shown = $user_dropdown.hasClass("show");

        if (!dropdown_is_shown) {
            $user_dropdown.addClass("show");
        } else if (dropdown_is_shown) {
            $user_dropdown.removeClass("show");
        }
    });
});
