import $ from "jquery";

// Add functions to this that have no non-trivial
// dependencies other than jQuery.

export function change_tab_to(tabname: string): void {
    $(`#gear-menu a[href="${CSS.escape(tabname)}"]`).tab("show");
}

// https://stackoverflow.com/questions/4233265/contenteditable-set-caret-at-the-end-of-the-text-cross-browser
export function place_caret_at_end(el: HTMLElement): void {
    el.focus();

    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    const sel = window.getSelection();
    sel?.removeAllRanges();
    sel?.addRange(range);
}

export function blur_active_element(): void {
    // this blurs anything that may perhaps be actively focused on.
    if (document.activeElement instanceof HTMLElement) {
        document.activeElement.blur();
    }
}

export function convert_enter_to_click(e: JQuery.KeyDownEvent): void {
    if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        $(e.currentTarget).trigger("click");
    }
}

export function update_unread_count_in_dom(unread_count_elem: JQuery, count: number): void {
    // This function is used to update unread count in top left corner
    // elements.
    const unread_count_span = unread_count_elem.find(".unread_count");

    if (count === 0) {
        unread_count_span.hide();
        unread_count_span.text("");
        return;
    }

    unread_count_span.show();
    unread_count_span.text(count);
}
