/* Module for popovers that have been ported to the modern
   TippyJS/Popper popover library from the legacy Bootstrap
   popovers system in popovers.js. */

import $ from "jquery";
import * as tippy from "tippy.js";

import * as blueslip from "./blueslip.ts";
import * as message_viewport from "./message_viewport.ts";
import * as modals from "./modals.ts";
import * as overlays from "./overlays.ts";
import * as popovers from "./popovers.ts";
import * as ui_util from "./ui_util.ts";
import * as util from "./util.ts";

type PopoverName =
    | "compose_control_buttons"
    | "starred_messages"
    | "drafts"
    | "left_sidebar_inbox_popover"
    | "left_sidebar_all_messages_popover"
    | "left_sidebar_recent_view_popover"
    | "top_left_sidebar"
    | "message_actions"
    | "stream_card_popover"
    | "stream_settings"
    | "topics_menu"
    | "send_later"
    | "change_visibility_policy"
    | "personal_menu"
    | "gear_menu"
    | "help_menu"
    | "buddy_list"
    | "stream_actions_popover"
    | "color_picker_popover";

export const popover_instances: Record<PopoverName, tippy.Instance | null> = {
    compose_control_buttons: null,
    starred_messages: null,
    drafts: null,
    left_sidebar_inbox_popover: null,
    left_sidebar_all_messages_popover: null,
    left_sidebar_recent_view_popover: null,
    top_left_sidebar: null,
    message_actions: null,
    stream_card_popover: null,
    stream_settings: null,
    topics_menu: null,
    send_later: null,
    change_visibility_policy: null,
    personal_menu: null,
    gear_menu: null,
    help_menu: null,
    buddy_list: null,
    stream_actions_popover: null,
    color_picker_popover: null,
};

// Font size in em for popover derived from popover font size being
// 15px at base font size of 14px.
export const POPOVER_FONT_SIZE_IN_EM = 1.0714;

/* Keyboard UI functions */
export function popover_items_handle_keyboard(key: string, $items?: JQuery): void {
    if (!$items) {
        return;
    }

    const index = $items.index($items.filter(":focus"));

    if (key === "enter") {
        // This is not enough for some elements which need to trigger
        // natural click for them to work like ClipboardJS and follow
        // the link for anchor tags. For those elements, we need to
        // use `.navigate-link-on-enter` class on them.
        $items.eq(index).trigger("click");
        return;
    }

    if (key === "down_arrow" || key === "vim_down") {
        [...$items]
            .slice(index === -1 ? 0 : index + 1)
            .find((item) => item.getClientRects().length)
            ?.focus();
    } else if (key === "up_arrow" || key === "vim_up") {
        [...$items]
            .slice(0, index === -1 ? $items.length : index)
            .findLast((item) => item.getClientRects().length)
            ?.focus();
    }
}

export function focus_first_popover_item($items: JQuery | undefined, index = 0): void {
    if (!$items) {
        return;
    }

    $items.eq(index).expectOne().trigger("focus");
}

export function sidebar_menu_instance_handle_keyboard(instance: tippy.Instance, key: string): void {
    const items = get_popover_items_for_instance(instance);
    popover_items_handle_keyboard(key, items);
}

export function get_visible_instance(): tippy.Instance | null | undefined {
    return Object.values(popover_instances).find(Boolean);
}

export function get_topic_menu_popover(): tippy.Instance | null {
    return popover_instances.topics_menu;
}

export function is_topic_menu_popover_displayed(): boolean {
    return popover_instances.topics_menu?.state.isVisible ?? false;
}

export function is_visibility_policy_popover_displayed(): boolean {
    return popover_instances.change_visibility_policy?.state.isVisible ?? false;
}

export function get_scheduled_messages_popover(): tippy.Instance | null {
    return popover_instances.send_later;
}

export function is_scheduled_messages_popover_displayed(): boolean {
    return popover_instances.send_later?.state.isVisible ?? false;
}

export function get_starred_messages_popover(): tippy.Instance | null {
    return popover_instances.starred_messages;
}

export function is_personal_menu_popover_displayed(): boolean {
    return popover_instances.personal_menu?.state.isVisible ?? false;
}

export function is_gear_menu_popover_displayed(): boolean {
    return popover_instances.gear_menu?.state.isVisible ?? false;
}

export function get_gear_menu_instance(): tippy.Instance | null {
    return popover_instances.gear_menu;
}

export function is_help_menu_popover_displayed(): boolean {
    return popover_instances.help_menu?.state.isVisible ?? false;
}

export function is_message_actions_popover_displayed(): boolean {
    return popover_instances.message_actions?.state.isVisible ?? false;
}

export function get_stream_actions_popover(): tippy.Instance | null {
    return popover_instances.stream_actions_popover;
}

export function is_stream_actions_popover_displayed(): boolean | undefined {
    return popover_instances.stream_actions_popover?.state.isVisible;
}

export function get_color_picker_popover(): tippy.Instance | null {
    return popover_instances.color_picker_popover;
}

export function is_color_picker_popover_displayed(): boolean | undefined {
    return popover_instances.color_picker_popover?.state.isVisible;
}

export function get_popover_items_for_instance(instance: tippy.Instance): JQuery | undefined {
    const $current_elem = $(instance.popper);
    const class_name = $current_elem.attr("class");

    if (!$current_elem) {
        blueslip.error("Trying to get menu items when popover is closed.", {class_name});
        return undefined;
    }

    return $current_elem.find("a, [tabindex='0']");
}

export function hide_current_popover_if_visible(instance: tippy.Instance | null): void {
    // Call this function instead of `instance.hide` to avoid tippy
    // logging about the possibility of already hidden instances,
    // which can occur when a click handler does a hide_all().
    if (instance?.state.isVisible) {
        instance.hide();
    }
}

export const default_popover_props: Partial<tippy.Props> = {
    delay: 0,
    appendTo: () => document.body,
    trigger: "click",
    interactive: true,
    hideOnClick: true,
    /* The light-border TippyJS theme is a bit of a misnomer; it
       is a popover styling similar to Bootstrap.  We've also customized
       its CSS to support Zulip's dark theme. */
    theme: "light-border",
    // The maxWidth has been set to "none" to avoid the default value of 300px.
    maxWidth: "none",
    touch: true,
    /* Don't use allow-HTML here since it is unsafe. Instead, use `parse_html`
       to generate the required html */
    popperOptions: {
        modifiers: [
            {
                // Hide popover for which the reference element is hidden.
                // References:
                // https://popper.js.org/docs/v2/modifiers/
                // https://github.com/atomiks/tippyjs/blob/ad85f6feb79cf6c5853c43bf1b2a50c4fa98e7a1/src/createTippy.ts#L608
                name: "destroy-popover-if-reference-hidden",
                enabled: true,
                phase: "beforeWrite",
                requires: ["$$tippy"],
                fn({state}) {
                    // Since the reference element can be removed from DOM, we rely on popper
                    // here to access the tippy instance which is reliable.
                    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
                    const instance = (state.elements.popper as tippy.PopperElement)._tippy!;
                    const $popover = $(state.elements.popper);
                    const $tippy_box = $popover.find(".tippy-box");
                    // $tippy_box[0].hasAttribute("data-reference-hidden"); is the real check
                    // but linter wants us to write it like this.
                    const is_reference_outside_window = Object.hasOwn(
                        util.the($tippy_box).dataset,
                        "referenceHidden",
                    );

                    if ($tippy_box.hasClass("show-when-reference-hidden")) {
                        // Show user card popover as an overlay if we are not sure about position of the
                        // reference. This can happen when popover reference has been replaced or hidden.
                        if (
                            is_reference_outside_window &&
                            $tippy_box.find("#user_card_popover").length > 0
                        ) {
                            $("body").append($("<div>").attr("id", "popover-overlay-background"));
                            instance.setProps(get_props_for_popover_centering(instance.props));
                        }
                        return;
                    }

                    if (is_reference_outside_window) {
                        hide_current_popover_if_visible(instance);
                        return;
                    }

                    const $reference = $(state.elements.reference);
                    // Hide popover if the reference element is below another element.
                    //
                    // We only care about the reference element if it is inside the message feed since
                    // hiding elements outside the message feed is tricky and expensive due to stacking context.
                    // References in overlays, modal, sidebar overlays, popovers, etc. can make the below logic hard
                    // to live with if we take elements outside message feed into account.
                    // Since `.sticky_header` is inside `#message_feed_container`, we allow popovers from reference inside
                    // `.sticky_header` to be visible.
                    if (
                        $reference.parents("#message_feed_container, .sticky_header").length !== 1
                    ) {
                        return;
                    }

                    const reference_rect = util.the($reference).getBoundingClientRect();
                    // This is the logic we want but since it is too expensive to run
                    // on every scroll, we run a cheaper version of this to just check if
                    // compose, sticky header or navbar are not obscuring the reference
                    // in message list where we want a better experience.
                    // Also, elementFromPoint can be quite buggy since element can be temporarily
                    // hidden or obscured by other elements like `simplebar-wrapper`.
                    //
                    // const topmost_element = document.elementFromPoint(
                    //     reference_rect.left,
                    //     reference_rect.top,
                    // );
                    // if (
                    //     !topmost_element ||
                    //     ($(topmost_element).closest($reference).length === 0 &&
                    //         $(topmost_element).find($reference).length === 0)
                    // ) {
                    //     instance.hide();
                    // }

                    // Hide popover if the reference element is below compose, sticky header or navbar.

                    // These are elements covering the reference element (intersection of elements at top
                    // top left and bottom right)
                    const elements_at_reference_position = document
                        .elementsFromPoint(reference_rect.left, reference_rect.top)
                        .filter((element) =>
                            document
                                .elementsFromPoint(reference_rect.right, reference_rect.bottom)
                                .includes(element),
                        );

                    if (
                        elements_at_reference_position.some(
                            (element) =>
                                element.id === "navbar-fixed-container" ||
                                element.id === "compose-content" ||
                                element.classList.contains("sticky_header"),
                        )
                    ) {
                        hide_current_popover_if_visible(instance);
                    }
                },
            },
        ],
    },
};

export const left_sidebar_tippy_options: Partial<tippy.Props> = {
    theme: "popover-menu",
    placement: "right",
    popperOptions: {
        modifiers: [
            {
                name: "flip",
                options: {
                    fallbackPlacements: ["bottom", "top", "left"],
                },
            },
        ],
    },
};

export function on_show_prep(instance: tippy.Instance): void {
    $(instance.popper).on("click", (e) => {
        // Popover is not hidden on click inside it unless the click handler for the
        // element explicitly hides the popover when handling the event.
        // `stopPropagation` is required here to avoid global click handlers from
        // being triggered.
        e.stopPropagation();
    });
    $(instance.popper).one("click", ".navigate_and_close_popover", (e) => {
        // Handler for links inside popover which don't need a special click handler.
        e.stopPropagation();
        hide_current_popover_if_visible(instance);
    });
}

function get_props_for_popover_centering(
    popover_props: Partial<tippy.Props>,
): Partial<tippy.Props> {
    return {
        arrow: false,
        getReferenceClientRect: () => new DOMRect(0, 0, 0, 0),
        // Since we are resetting the reference to (0,0) in DOM the placement here doesn't matter
        // Using "bottom" placement as it works well with Popper's positioning system
        // when the popover exceeds window height
        placement: "bottom",
        popperOptions: {
            modifiers: [
                {
                    name: "offset",
                    options: {
                        offset({popper}: {popper: DOMRect}) {
                            // Calculate the offset needed to place the reference in the center
                            const x_offset_to_center = window.innerWidth / 2;
                            let y_offset_to_center = window.innerHeight / 2 - popper.height / 2;

                            // Move popover to the top of the screen if user is focused on an element which can
                            // open keyboard on a mobile device causing the screen to resize.
                            // Resize doesn't happen on iOS when keyboard is open, and typing text in input field just works.
                            // For other browsers, we need to check if the focused element is an text field and
                            // is causing a resize (thus calling this `offset` modifier function), in which case
                            // we need to move the popover to the top of the screen.
                            if (util.is_mobile()) {
                                const $focused_element = $(document.activeElement!);
                                if (
                                    $focused_element.is(
                                        "input[type=text], input[type=number], textarea",
                                    )
                                ) {
                                    y_offset_to_center = 10;
                                }
                            }
                            return [x_offset_to_center, y_offset_to_center];
                        },
                    },
                },
            ],
        },
        onShow(instance) {
            // By default, Tippys with the `data-reference-hidden` attribute aren't displayed.
            // But when we render them as centered overlays on mobile and use
            // `getReferenceClientRect` for a virtual reference, Tippy slaps this
            // hidden attribute on our element, making it invisible. We want to bypass
            // this in scenarios where we're centering popovers on mobile screens.
            $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");
            if (popover_props.onShow) {
                popover_props.onShow(instance);
            }
        },
        onMount(instance) {
            $("body").append($("<div>").attr("id", "popover-overlay-background"));
            if (popover_props.onMount) {
                popover_props.onMount(instance);
            }
        },
        onHidden(instance) {
            $("#popover-overlay-background").remove();
            if (popover_props.onHidden) {
                popover_props.onHidden(instance);
            }
        },
    };
}

// Toggles a popover menu directly; intended for use in keyboard
// shortcuts and similar alternative ways to open a popover menu.
export function toggle_popover_menu(
    target: tippy.ReferenceElement,
    popover_props: Partial<tippy.Props>,
    options?: {
        show_as_overlay_on_mobile: boolean;
        show_as_overlay_always: boolean;
        // Only works for elements which are in message feed.
        message_feed_overlay_detection?: boolean;
    },
): tippy.Instance {
    const instance = target._tippy;
    if (instance) {
        // Ideally, we'd check that the _tippy object is a
        // popover. For elements that host both a Tippy tooltip and a
        // popover, this can incorrectly return early after hiding the
        // Tippy tooltip.
        //
        // If we fix this, we can remove a few popovers.hide_all calls.
        hide_current_popover_if_visible(instance);
        return instance;
    }

    let mobile_popover_props = {};

    // If the window is mobile-sized, we will render the
    // popover centered on the screen as an overlay.
    let show_as_overlay =
        (options?.show_as_overlay_on_mobile === true &&
            ui_util.matches_viewport_state("lt_md_min")) ||
        options?.show_as_overlay_always === true;

    // Show the popover as overlay if the reference element is hidden in message feed.
    if (
        !show_as_overlay &&
        options?.message_feed_overlay_detection &&
        $(target).parents("#message_feed_container").length === 1
    ) {
        const target_props = $(target).get_offset_to_window();
        const viewport_info = message_viewport.message_viewport_info();
        if (
            target_props.top < viewport_info.visible_top ||
            target_props.bottom > viewport_info.visible_bottom
        ) {
            show_as_overlay = true;
        }
    }

    if (show_as_overlay) {
        mobile_popover_props = {
            ...get_props_for_popover_centering(popover_props),
        };
    }

    if (popover_props.popperOptions?.modifiers) {
        popover_props.popperOptions.modifiers = [
            ...default_popover_props.popperOptions!.modifiers!,
            ...popover_props.popperOptions.modifiers,
        ];
    }

    return tippy.default(target, {
        ...default_popover_props,
        showOnCreate: true,
        ...popover_props,
        ...mobile_popover_props,
    });
}

// Main function to define a popover menu, opened via clicking on the
// target selector.
export function register_popover_menu(target: string, popover_props: Partial<tippy.Props>): void {
    // For some elements, such as the click target to open the message
    // actions menu, we want to avoid propagating the click event to
    // parent elements. Tippy's built-in `delegate` method does not
    // have an option to do stopPropagation, so we use this method to
    // open the Tippy popovers associated with such elements.
    //
    // A click on the click target will close the menu; for this to
    // work correctly without leaking, all callers need call
    // `instance.destroy()` inside their `onHidden` handler.
    //
    // TODO: Should we instead we wrap the caller's `onHidden` hook,
    // if any, to add `instance.destroy()`?
    $("body").on("click", target, function (this: HTMLElement, e) {
        e.preventDefault();
        e.stopPropagation();

        // Hide popovers when user clicks on an element which navigates user to a link.
        // We don't explicitly handle these clicks per element and let browser handle them but in doing so,
        // we are not able to hide the popover which we would do otherwise.
        const instance = toggle_popover_menu(this, popover_props);
        const $popper = $(instance.popper);
        $popper.on("click", "a[href]", () => {
            hide_current_popover_if_visible(instance);
        });
    });
}

export function initialize(): void {
    /* Configure popovers to hide when toggling overlays. */
    overlays.register_pre_open_hook(popovers.hide_all);
    overlays.register_pre_close_hook(popovers.hide_all);
    modals.register_pre_open_hook(popovers.hide_all);
    modals.register_pre_close_hook(popovers.hide_all);
}
