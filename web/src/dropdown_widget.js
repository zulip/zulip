import $ from "jquery";
import * as tippy from "tippy.js";

import render_dropdown_disabled_state from "../templates/dropdown_disabled_state.hbs";
import render_dropdown_list from "../templates/dropdown_list.hbs";
import render_dropdown_list_container from "../templates/dropdown_list_container.hbs";
import render_inline_decorated_stream_name from "../templates/inline_decorated_stream_name.hbs";

import * as blueslip from "./blueslip";
import * as ListWidget from "./list_widget";
import {default_popover_props} from "./popover_menus";
import {parse_html} from "./ui_util";

/* Sync with max-height set in zulip.css */
export const DEFAULT_DROPDOWN_HEIGHT = 210;
const noop = () => {};
export const DATA_TYPES = {
    NUMBER: "number",
    STRING: "string",
};

export class DropdownWidget {
    constructor({
        widget_name,
        get_options,
        item_click_callback,
        // Provide an parent element to widget which will be re-rendered if the widget is setup again.
        // It is important to not pass `$("body")` here for widgets that would be `setup()`
        // multiple times, so that we don't have duplicate event handlers.
        $events_container,
        on_show_callback = noop,
        on_mount_callback = noop,
        on_hidden_callback = noop,
        on_exit_with_escape_callback = noop,
        render_selected_option = noop,
        // Used to focus the `target` after dropdown is closed. This is important since the dropdown is
        // appended to `body` and hence `body` is focused when the dropdown is closed, which makes
        // it hard for the user to get focus back to the `target`.
        focus_target_on_hidden = true,
        tippy_props = {},
        // NOTE: Any value other than `null` will be rendered when class is initialized.
        default_id = null,
        unique_id_type = null,
        // Show disabled state if the default_id is not in `get_options()`.
        show_disabled_if_current_value_not_in_options = false,
    }) {
        this.widget_name = widget_name;
        this.widget_id = `#${CSS.escape(widget_name)}_widget`;
        // A widget wrapper may not exist based on the UI requirement.
        this.widget_wrapper_id = `${this.widget_id}_wrapper`;
        this.widget_value_selector = `${this.widget_id} .dropdown_widget_value`;
        this.get_options = get_options;
        this.item_click_callback = item_click_callback;
        this.focus_target_on_hidden = focus_target_on_hidden;
        this.on_show_callback = on_show_callback;
        this.on_mount_callback = on_mount_callback;
        this.on_hidden_callback = on_hidden_callback;
        this.on_exit_with_escape_callback = on_exit_with_escape_callback;
        this.render_selected_option = render_selected_option;
        this.tippy_props = tippy_props;
        this.list_widget = null;
        this.instance = null;
        this.default_id = default_id;
        this.current_value = default_id;
        this.unique_id_type = unique_id_type;
        this.$events_container = $events_container;
        this.show_disabled_if_current_value_not_in_options =
            show_disabled_if_current_value_not_in_options;
    }

    init() {
        if (this.current_value !== null) {
            this.render();
        }

        this.$events_container.on(
            "keydown",
            `${this.widget_id}, ${this.widget_wrapper_id}`,
            (e) => {
                if (e.key === "Enter") {
                    $(`${this.widget_id}`).trigger("click");
                    e.stopPropagation();
                    e.preventDefault();
                }
            },
        );
    }

    show_empty_if_no_items($popper) {
        const list_items = this.list_widget.get_current_list();
        const $no_search_results = $popper.find(".no-dropdown-items");
        if (list_items.length === 0) {
            $no_search_results.show();
        } else {
            $no_search_results.hide();
        }
    }

    setup() {
        this.init();
        const delegate_container = this.$events_container.get(0);
        if (!delegate_container) {
            blueslip.error(
                "Cannot initialize dropdown. `$events_container` empty.",
                this.$events_container,
            );
        }
        this.instance = tippy.delegate(delegate_container, {
            ...default_popover_props,
            target: this.widget_id,
            // Custom theme defined in popovers.css
            theme: "dropdown-widget",
            arrow: false,
            onShow: function (instance) {
                instance.setContent(parse_html(render_dropdown_list_container()));
                const $popper = $(instance.popper);
                const $dropdown_list_body = $popper.find(".dropdown-list");
                const $search_input = $popper.find(".dropdown-list-search-input");

                this.list_widget = ListWidget.create($dropdown_list_body, this.get_options(), {
                    name: `${CSS.escape(this.widget_name)}-list-widget`,
                    get_item: ListWidget.default_get_item,
                    modifier_html(item) {
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
                    this.show_empty_if_no_items($popper);
                });

                // Keyboard handler
                $popper.on("keydown", (e) => {
                    function trigger_element_focus($element) {
                        e.preventDefault();
                        e.stopPropagation();
                        // When bringing a non-visible element into view, scroll as minimum as possible.
                        $element[0]?.scrollIntoView({block: "nearest"});
                        $element.trigger("focus");
                    }

                    const $search_input = $popper.find(".dropdown-list-search-input");
                    const list_items = this.list_widget.get_current_list();
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

                    const render_all_items_and_focus_last_item = function () {
                        // List widget doesn't render all items by default, so we need to render all
                        // the items and focus on the last element.
                        const list_items = this.list_widget.get_current_list();
                        this.list_widget.render(list_items.length);
                        trigger_element_focus(last_item());
                    }.bind(this);

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
                            this.on_exit_with_escape_callback();
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
                    this.current_value = $(event.currentTarget).attr("data-unique-id");
                    if (this.unique_id_type === DATA_TYPES.NUMBER) {
                        this.current_value = Number.parseInt(this.current_value, 10);
                    }
                    this.item_click_callback(event, instance);
                });

                // Set focus on search input when dropdown opens.
                setTimeout(() => {
                    $(".dropdown-list-search-input").trigger("focus");
                });

                this.on_show_callback(instance);
            }.bind(this),
            onMount: function (instance) {
                this.show_empty_if_no_items($(instance.popper));
                this.on_mount_callback(instance);
            }.bind(this),
            onHidden: function (instance) {
                if (this.focus_target_on_hidden) {
                    $(this.widget_id).trigger("focus");
                }
                this.on_hidden_callback(instance);
                this.instance = null;
            }.bind(this),
            ...this.tippy_props,
        });
    }

    value() {
        return this.current_value;
    }

    // NOTE: This function needs to be explicitly called when you want to update the
    // current value of the widget. We don't call this automatically since some of our
    // dropdowns don't need it. Maybe we can follow a reverse approach in the future.
    render(value) {
        // Check if the value is valid otherwise just render previous value.
        if (typeof value === typeof this.current_value) {
            this.current_value = value;
        }

        const all_options = this.get_options();
        let option = all_options.find((option) => option.unique_id === this.current_value);

        // Show disabled if cannot find current option.
        if (!option && this.show_disabled_if_current_value_not_in_options) {
            option = all_options.find((option) => option.is_setting_disabled === true);
        }

        if (!option) {
            blueslip.error(`Cannot find current value: ${this.current_value} in provided options.`);
            return;
        }

        if (option.is_setting_disabled) {
            $(this.widget_value_selector).html(render_dropdown_disabled_state({name: option.name}));
        } else if (option.stream) {
            $(this.widget_value_selector).html(
                render_inline_decorated_stream_name({
                    stream: option.stream,
                    show_colored_icon: true,
                }),
            );
        } else {
            $(this.widget_value_selector).text(option.name);
        }
    }
}
