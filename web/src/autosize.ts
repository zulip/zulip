/**
 * This module supports the CSS Grid-based autosize implementation.
 *
 * Instead of calculating pixel heights in JavaScript,
 * this module simply copies the textarea's value to a `data-replicated-value`
 * attribute on the parent container.
 *
 * The CSS in `compose.css` and `message_row.css` uses this attribute to populate a hidden pseudo-element
 * that forces the grid container to grow, naturally resizing the textarea.
 */

export function watch($textarea: JQuery<HTMLTextAreaElement>): void {
    const textarea = $textarea[0];
    if (!textarea) {
        return;
    }

    // Check if we have already wrapped this specific textarea
    let $parent = $textarea.parent?.();

    if (!$parent || $parent.length === 0 || !$parent.hasClass("autosize-container")) {
        $textarea.wrap('<div class="autosize-container"></div>');
        $parent = $textarea.parent();
    }

    // The logic: Sync value to data attribute on input so CSS can read it
    const update = (): void => {
        const val = $textarea.val()!;
        $parent.attr("data-replicated-value", val);
    };

    $textarea.on("input", update);

    // Initial sync
    update();
}

export function manual_resize($textarea: JQuery<HTMLTextAreaElement>): void {
    $textarea.trigger("input");
}
