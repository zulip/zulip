import $ from "jquery";

import * as navigation_views from "./navigation_views.ts";

function handle_checkbox_change(fragment: string, is_pinned: boolean): void {
    const $checkbox = $(`.navigation-view-checkbox[data-fragment="${fragment}"]`);
    
    navigation_views.set_view_pinned_status(
        fragment,
        is_pinned,
        () => {
            // Success - checkbox state is already correct
            console.log("Success - checkbox state is already correct");
        },
        () => {
            // Error - revert checkbox state
            $checkbox.prop("checked", !is_pinned);
            console.log("Error - revert checkbox state");
        },
    );
}

export function set_up(): void {
    $(document).on("change", "#navigation-views-table .navigation-view-checkbox", (e) => {
        e.stopPropagation();
        e.preventDefault();
        const $checkbox = $(e.target);
        const fragment = $checkbox.data("fragment") as string;
        const is_pinned = $checkbox.is(":checked");

        handle_checkbox_change(fragment, is_pinned);
    });
}
