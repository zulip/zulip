import $ from "jquery";

// Add functions to this that have no non-trivial
// dependencies other than jQuery.

export function change_tab_to(tabname) {
    $(`#gear-menu a[href="${CSS.escape(tabname)}"]`).tab("show");
}

// https://stackoverflow.com/questions/4233265/contenteditable-set-caret-at-the-end-of-the-text-cross-browser
export function place_caret_at_end(el) {
    el.focus();

    if (window.getSelection !== undefined && document.createRange !== undefined) {
        const range = document.createRange();
        range.selectNodeContents(el);
        range.collapse(false);
        const sel = window.getSelection();
        sel.removeAllRanges();
        sel.addRange(range);
    } else if (document.body.createTextRange !== undefined) {
        const textRange = document.body.createTextRange();
        textRange.moveToElementText(el);
        textRange.collapse(false);
        textRange.select();
    }
}

export function blur_active_element() {
    // this blurs anything that may perhaps be actively focused on.
    document.activeElement.blur();
}

export function convert_enter_to_click(e) {
    const key = e.which;
    if (key === 13) {
        // Enter
        $(e.currentTarget).trigger("click");
    }
}

export function update_unread_count_in_dom(unread_count_elem, count) {
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
