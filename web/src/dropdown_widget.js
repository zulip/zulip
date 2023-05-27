import $ from "jquery";
import * as tippy from "tippy.js";

import render_dropdown_list from "../templates/dropdown_list.hbs";
import render_dropdown_list_container from "../templates/dropdown_list_container.hbs";

import * as ListWidget from "./list_widget";
import {default_popover_props} from "./popover_menus";
import {parse_html} from "./ui_util";

/* Sync with max-height set in zulip.css */
export const DEFAULT_DROPDOWN_HEIGHT = 210;
const noop = () => {};

export function setup(tippy_props, get_options, item_click_callback, dropdown_props = {}) {
    // Define all possible `dropdown_props` here so that they are easy to track.
    const on_show_callback = dropdown_props.on_show_callback || noop;
    const on_hidden_callback = dropdown_props.on_hidden_callback || noop;
    const on_exit_with_escape_callback = dropdown_props.on_exit_with_escape_callback || noop;
    // Used to focus the `target` after dropdown is closed. This is important since the dropdown is
    // appended to `body` and hence `body` is focused when the dropdown is closed, which makes
    // it hard for the user to get focus back to the `target`.
    const focus_target_on_hidden = dropdown_props.focus_target_on_hidden || true;
    // Should enter keypress on target show the dropdown.
    const show_on_target_enter_keypress = dropdown_props.show_on_target_enter_keypress || false;

    if (show_on_target_enter_keypress) {
        $("body").on("keypress", tippy_props.target, (e) => {
            if (e.key === "Enter") {
                $(tippy_props.target).trigger("click");
                e.stopPropagation();
                e.preventDefault();
            }
        });
    }

    tippy.delegate("body", {
        ...default_popover_props,
        // Custom theme defined in popovers.css
        theme: "dropdown-widget",
        arrow: false,
        onShow(instance) {
            instance.setContent(parse_html(render_dropdown_list_container()));
            const $popper = $(instance.popper);
            const $dropdown_list_body = $popper.find(".dropdown-list");
            const $search_input = $popper.find(".dropdown-list-search-input");

            const list_widget = ListWidget.create($dropdown_list_body, get_options(), {
                name: `${CSS.escape(tippy_props.target)}-list-widget`,
                modifier(item) {
                    return render_dropdown_list({item});
                },
                filter: {
                    $element: $search_input,
                    predicate(item, value) {
                        return item.name.toLowerCase().includes(value);
                    },
                },
                $simplebar_container: $popper.find(".dropdown-list-wrapper"),
            });

            $search_input.on("input.list_widget_filter", () => {
                const list_items = list_widget.get_current_list();
                const $no_search_results = $popper.find(".no-dropdown-items");
                if (list_items.length === 0) {
                    $no_search_results.show();
                } else {
                    $no_search_results.hide();
                }
            });

            // Keyboard handler
            $popper.on("keydown", (e) => {
                function trigger_element_focus($element) {
                    e.preventDefault();
                    e.stopPropagation();
                    // When brining a non-visible element into view, scroll as minimum as possible.
                    $element[0]?.scrollIntoView({block: "nearest"});
                    $element.trigger("focus");
                }

                const $search_input = $popper.find(".dropdown-list-search-input");
                const list_items = list_widget.get_current_list();
                if (list_items.length === 0 && !(e.key === "Escape")) {
                    // Let the browser handle it.
                    return;
                }

                function first_item() {
                    const first_item = list_items[0];
                    return $popper.find(`.list-item[data-unique-id="${first_item.unique_id}"]`);
                }

                function last_item() {
                    const last_item = list_items.at(-1);
                    return $popper.find(`.list-item[data-unique-id="${last_item.unique_id}"]`);
                }

                function render_all_items_and_focus_last_item() {
                    // List widget doesn't render all items by default, so we need to render all
                    // the items and focus on the last element.
                    const list_items = list_widget.get_current_list();
                    list_widget.render(list_items.length);
                    trigger_element_focus(last_item());
                }

                switch (e.key) {
                    case "Enter":
                        if (e.target === $search_input.get(0)) {
                            // Select first item if in search input.
                            first_item().trigger("click");
                        } else if (list_items.length !== 0) {
                            $(e.target).trigger("click");
                        }
                        e.stopPropagation();
                        e.preventDefault();
                        break;

                    case "Escape":
                        instance.hide();
                        on_exit_with_escape_callback();
                        e.stopPropagation();
                        e.preventDefault();
                        break;

                    case "Tab":
                    case "ArrowDown":
                        switch (e.target) {
                            case last_item().get(0):
                                trigger_element_focus($search_input);
                                break;
                            case $search_input.get(0):
                                trigger_element_focus(first_item());
                                break;
                            default:
                                trigger_element_focus($(e.target).next());
                        }
                        break;

                    case "ArrowUp":
                        switch (e.target) {
                            case first_item().get(0):
                                trigger_element_focus($search_input);
                                break;
                            case $search_input.get(0):
                                render_all_items_and_focus_last_item();
                                break;
                            default:
                                trigger_element_focus($(e.target).prev());
                        }
                        break;
                }
            });

            // Click on item.
            $popper.one("click", ".list-item", (event) => {
                item_click_callback(event, instance);
            });

            // Set focus on search input when dropdown opens.
            setTimeout(() => {
                $(".dropdown-list-search-input").trigger("focus");
            });

            on_show_callback(instance);
        },
        onHidden(instance) {
            if (focus_target_on_hidden) {
                $(tippy_props.target).trigger("focus");
            }
            on_hidden_callback(instance);
        },
        ...tippy_props,
    });
}
