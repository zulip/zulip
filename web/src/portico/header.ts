import {$} from "jquery";

const EXTRA_SUBMENU_BOTTOM_PADDING = 16;

$(() => {
    // The closed mobile menu lands below the banner for free via
    // top: auto in CSS. When the user opens the menu, we keep the
    // banner visible above it: push the open panel down by the
    // banner's actual rendered height so it survives the announcement
    // wrapping onto multiple lines on narrow viewports. The observer
    // is only attached while the menu is open, so the steady-state
    // page pays nothing for it.
    const banner = document.querySelector<HTMLElement>("#navbar-custom-message");
    const mobile_menu_toggle = document.querySelector<HTMLInputElement>("#top-menu-mobile-toggle");
    if (banner && mobile_menu_toggle) {
        const update_banner_height = (): void => {
            document.documentElement.style.setProperty(
                "--announcement-banner-height",
                `${banner.offsetHeight}px`,
            );
        };
        const observer = new ResizeObserver(update_banner_height);
        mobile_menu_toggle.addEventListener("change", () => {
            if (mobile_menu_toggle.checked) {
                update_banner_height();
                observer.observe(banner);
            } else {
                observer.disconnect();
            }
        });
    }

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
                el.offsetHeight + EXTRA_SUBMENU_BOTTOM_PADDING,
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

    $(".top-menu-tab-input").on("click", function () {
        on_tab_menu_selection_change(this);
    });

    $(".top-menu-tab-unselect").on("click", () => {
        on_top_menu_tab_unselect_click();
    });

    // Once a menu is open, resting the pointer on another menu's label
    // switches to it, like a desktop menu bar. The delay avoids
    // switching when the pointer only crosses a label on its way into
    // the open menu. The width matches the breakpoint in navbar.css.
    const HOVER_SWITCH_DELAY_MS = 150;
    const wide_layout_with_hover = window.matchMedia("(width > 1100px) and (hover: hover)");
    let hover_switch_timer: ReturnType<typeof setTimeout> | undefined;
    $(".top-menu-tab > .nav-menu-label").on("mouseenter", function () {
        const $menu_input = $(`#${CSS.escape($(this).attr("for")!)}`);
        const is_another_menu_open = $(".top-menu-tab-input:checked").not($menu_input).length > 0;
        if (wide_layout_with_hover.matches && is_another_menu_open) {
            hover_switch_timer = setTimeout(() => {
                $menu_input.trigger("click");
            }, HOVER_SWITCH_DELAY_MS);
        }
    });
    $(".top-menu-tab > .nav-menu-label").on("mouseleave", () => {
        clearTimeout(hover_switch_timer);
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
});
