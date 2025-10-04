import $ from "jquery";

export function collapse_or_expand({
    toggle_class,
    // Element which stores the toggle class and is being expanded/collapsed.
    $toggle_container,
    // Element which will be shown/hidden.
    $content,
    // List of all the elements including the toggle container and content.
    // If rows other than toggle container and content could be grouped,
    // provide the parent container instead of the individual rows.
    $all_elements,
    // Duration of the animation in milliseconds.
    duration,
}: {
    toggle_class: string;
    $toggle_container: JQuery;
    $content: JQuery;
    $all_elements: JQuery;
    duration: number;
}): void {
    // We use a blocker to avoid any content from being
    // visible below the last item. This function assumes
    // that blocker is always the last element.
    const $blocker = $all_elements.last();
    // Expand the container.
    if ($toggle_container.hasClass(toggle_class)) {
        $toggle_container.removeClass(toggle_class);
        // Will be used to animte opacity from 0 to 1.
        $content.css("opacity", "0");

        const height = $content.outerHeight();
        // Set height of the blocker to the height of the content,
        // to avoid any content from showing below the last element.
        $blocker.css("height", `${height}px`);

        // Move all the elements below the $toggle_container up
        // by the height of the $content.
        let found_container_wrapper = false;
        $all_elements.each((_index, elt) => {
            if (found_container_wrapper) {
                $(elt).css({
                    position: "relative",
                    transform: `translateY(-${height}px)`,
                    "z-index": 1,
                });
            }
            if (elt === $content[0]) {
                found_container_wrapper = true;
            }
        });

        // Force the browser to reflow the page so that the transform is applied.
        // eslint-disable-next-line @typescript-eslint/no-unused-expressions
        $content[0]!.offsetHeight;
        found_container_wrapper = false;
        $all_elements.each((_index, elt) => {
            if (found_container_wrapper) {
                $(elt).css({
                    transform: `translateY(0)`,
                    transition: "transform 0.2s ease-in-out",
                });
            }
            if (elt === $content[0]) {
                found_container_wrapper = true;
                $(elt).css({
                    opacity: "1",
                    transition: "opacity 0.2s ease-in-out",
                });
            }
        });
    } else {
        // Collapse the container.
        const height = $content.outerHeight();
        $blocker.css("height", `${height}px`);
        $content.css("opacity", "1");
        let found_container_wrapper = false;
        $all_elements.each((_index, elt) => {
            if (found_container_wrapper) {
                $(elt).css({
                    position: "relative",
                    "z-index": 1,
                    transform: `translateY(-${height}px)`,
                    transition: "transform 0.2s ease-in-out",
                });
            }
            if (elt === $content[0]) {
                found_container_wrapper = true;
                $(elt).css({
                    opacity: "0",
                    transition: "opacity 0.2s ease-in-out",
                });
            }
        });
        setTimeout(() => {
            $toggle_container.addClass(toggle_class);
        }, duration);
    }

    // Reset
    setTimeout(() => {
        $all_elements.each((_index, elt) => {
            $(elt).css({
                position: "",
                "z-index": "",
                transform: "",
                transition: "",
                opacity: "",
            });
        });
        $blocker.css("height", "");
    }, duration);
}
