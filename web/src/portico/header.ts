import $ from "jquery";

const EXTRA_SUBMENU_BOTTOM_PADDING = 16;

$(() => {
    function on_tab_menu_selection_change(changed_element?: HTMLElement): void {
        // Pass event to open menu and if it is undefined, we close the menu.
        if (!changed_element) {
            $("#top-menu-submenu-backdrop").css("height", "0px");
            return;
        }
        const el = changed_element.parentElement!.querySelector<HTMLElement>(".top-menu-submenu");
        if (el) {
            $("#top-menu-submenu-backdrop").css(
                "height",
                Number(el.offsetHeight) + EXTRA_SUBMENU_BOTTOM_PADDING,
            );
        } else {
            $("#top-menu-submenu-backdrop").css("height", 0);
        }
    }

    function on_top_menu_tab_unselect_click(): void {
        // Close the menu.
        $("#top-menu-tab-close").prop("checked", true);
        on_tab_menu_selection_change();
    }

    function update_submenu_height_if_visible(): void {
        if ($(".top-menu-tab-input:checked").length === 1) {
            const sub_menu_height =
                $(".top-menu-tab-input:checked ~ .top-menu-submenu").height() ?? 0;
            $("#top-menu-submenu-backdrop").css(
                "height",
                sub_menu_height + EXTRA_SUBMENU_BOTTOM_PADDING,
            );
        }
    }

    // In case user presses `back` with menu open.
    // See https://github.com/zulip/zulip/pull/24301#issuecomment-1418547337.
    update_submenu_height_if_visible();

    // Update the height again if window is resized.
    $(window).on("resize", () => {
        update_submenu_height_if_visible();
    });

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

    $(".top-menu-tab-input").on("click", function (this: HTMLElement) {
        on_tab_menu_selection_change(this);
    });

    $(".top-menu-tab-unselect").on("click", () => {
        on_top_menu_tab_unselect_click();
    });

    $("#top-menu-tab-close").on("change", () => {
        on_tab_menu_selection_change();
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

    /* Used by navbar of non-corporate URLs. */
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
});
