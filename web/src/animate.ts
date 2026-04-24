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

        const height = $content.outerHeight();
        // Set height of the blocker to the height of the content,
        // to avoid any content from showing below the last element.
        $blocker.css("height", `${height}px`);
        $content.addClass("content-expand-animation-start");

        let found_container_wrapper = false;
        // Move all the elements below the $toggle_container up
        // by the height of the $content.
        $all_elements.each((_index, elt) => {
            if (found_container_wrapper) {
                $(elt).addClass("mark-element-for-translation");
                $(elt).css({
                    transform: `translateY(-${height}px)`,
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
                $content
                    .addClass("content-expand-animation-end")
                    .removeClass("content-expand-animation-start");
            }
        });
    } else {
        // Collapse the container.
        const height = $content.outerHeight();
        $blocker.css("height", `${height}px`);
        $content.addClass("content-collapse-animation-start");
        let found_container_wrapper = false;
        $all_elements.each((_index, elt) => {
            if (found_container_wrapper) {
                $(elt).addClass("mark-element-for-translation");
                $(elt).css({
                    transform: `translateY(-${height}px)`,
                    transition: "transform 0.2s ease-in-out",
                });
            }
            if (elt === $content[0]) {
                found_container_wrapper = true;
                $content
                    .addClass("content-collapse-animation-end")
                    .removeClass("content-collapse-animation-start");
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
                transform: "",
                transition: "",
            });
            $(elt).removeClass("mark-element-for-translation");
        });
        $blocker.css("height", "");
        $content.removeClass(
            "content-expand-animation-start content-expand-animation-endcontent-collapse-animation-start content-collapse-animation-end",
        );
    }, duration);
}
