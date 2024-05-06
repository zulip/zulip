import $ from "jquery";
import tippy from "tippy.js";

import {parse_html} from "./ui_util";

export function initTippyTypeahead(
    $element: JQuery<HTMLInputElement>,
    suggestions: string[],
    placement:
        | "top"
        | "bottom"
        | "left"
        | "right"
        | "top-start"
        | "bottom-start"
        | "top-end"
        | "bottom-end" = "bottom-start",
): void {
    // Initialize tippy for typeahead
    const matches = suggestions.filter((item) =>
        item.toLowerCase().includes($element.val()!.toLowerCase()),
    );
    const tooltip = tippy($element.get(0)!, {
        content: parse_html(
            "<div>" +
                matches
                    .map((match) => `<div class="tippy-typeahead-suggestion">${match}</div>`)
                    .join("") +
                "</div>",
        ),
        trigger: "focus",
        placement,
        arrow: false,
        interactive: true,
    });

    $element.on("focus", () => {
        tooltip.show();
    });

    $element.on("input", function () {
        const query = $(this).val()!.toLowerCase();
        const matches = suggestions.filter((item) => item.toLowerCase().includes(query));
        if (matches.length > 0) {
            const tooltipContent = matches
                .map((match) => `<div class="tippy-typeahead-suggestion">${match}</div>`)
                .join("");
            tooltip.setContent(parse_html("<div>" + tooltipContent + "</div>"));
            tooltip.show();
        } else {
            tooltip.hide();
        }
    });

    $element.parent().on("click", ".tippy-typeahead-suggestion", function () {
        const suggestion = $(this).text();
        $element.val(suggestion);
        tooltip.hide();
    });
}
