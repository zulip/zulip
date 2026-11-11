import {$} from "jquery";

export function disable_scrolling(): void {
    // Why disable scrolling?
    // Since fixed / absolute positioned elements don't capture the scroll event unless
    // they overflow their defined container. Since fixed / absolute elements are not treated
    // as part of the document flow, we cannot capture `scroll` events on them and prevent propagation
    // as event bubbling doesn't work naturally.
    const scrollbar_width = window.innerWidth - document.documentElement.clientWidth;
    $(":root").css({"overflow-y": "hidden", "--disabled-scrollbar-width": `${scrollbar_width}px`});
}

export function enable_scrolling(): void {
    $(":root").css({"overflow-y": "scroll", "--disabled-scrollbar-width": "0px"});
}

export const OVERLAY_FOCUSABLE_SELECTOR =
    "input, button, select, .input, .sidebar-item, .ind-tab.first, a[href], a[tabindex='0'], .overlay-message-info-box";

export function get_visible_focusable_elements_in_overlay_container(
    $container: JQuery,
): HTMLElement[] {
    const visible_focusable_elements = [...$(OVERLAY_FOCUSABLE_SELECTOR, $container)].filter(
        (element) =>
            element.getClientRects().length > 0 &&
            $(element).css("visibility") !== "hidden" &&
            !$(element).is(":disabled"),
    );
    return visible_focusable_elements;
}

function selection_has_text(selection: Selection): boolean {
    // Unlike Selection.toString(), the text content of the selected
    // ranges doesn't include the alt text of selected images, which
    // Firefox includes.
    for (let i = 0; i < selection.rangeCount; i += 1) {
        if (selection.getRangeAt(i).cloneContents().textContent.trim() !== "") {
            return true;
        }
    }
    return false;
}

function move_textless_selection_to_start_of_element(element: HTMLElement): void {
    const selection = document.getSelection();
    if (
        selection?.focusNode &&
        element.contains(selection.focusNode) &&
        !selection_has_text(selection)
    ) {
        selection.collapse(element, 0);
    }
}

export function wrap_overlay_tab_focus(
    shift_key: boolean,
    focusable_elements: HTMLElement[],
): boolean {
    if (focusable_elements.length === 0) {
        // Nothing focusable inside the overlay; keep Tab trapped within it.
        return true;
    }

    const active_element =
        document.activeElement instanceof HTMLElement ? document.activeElement : null;
    const focus_is_in_overlay =
        active_element !== null && focusable_elements.includes(active_element);
    const first_element = focusable_elements[0]!;
    const last_element = focusable_elements.at(-1)!;

    if (focus_is_in_overlay) {
        // Firefox starts Tab navigation from the selection when it's
        // inside the focused element, rather than from the element
        // itself, and a caret or a selection of no text, such as from
        // clicking empty space or selecting an image, can be anywhere
        // in it. Move such a selection to the start of the element; a
        // selection of actual text is kept.
        move_textless_selection_to_start_of_element(active_element);
    }

    if (shift_key) {
        if (active_element === first_element || !focus_is_in_overlay) {
            last_element.focus();
            return true;
        }
    } else if (active_element === last_element || !focus_is_in_overlay) {
        first_element.focus();
        return true;
    }

    return false;
}
