import $ from "jquery";
import assert from "minimalistic-assert";
import * as tippy from "tippy.js";

import render_dropdown_current_value_not_in_options from "../templates/dropdown_current_value_not_in_options.hbs";
import render_dropdown_disabled_state from "../templates/dropdown_disabled_state.hbs";
import render_dropdown_list from "../templates/dropdown_list.hbs";
import render_dropdown_list_container from "../templates/dropdown_list_container.hbs";
import render_inline_decorated_channel_name from "../templates/inline_decorated_channel_name.hbs";

import * as blueslip from "./blueslip.ts";
import * as ListWidget from "./list_widget.ts";
import type {ListWidget as ListWidgetType} from "./list_widget.ts";
import {page_params} from "./page_params.ts";
import * as popover_menus from "./popover_menus.ts";
import type {StreamSubscription} from "./sub_store.ts";
import {parse_html} from "./ui_util.ts";
import * as util from "./util.ts";

/* Sync with max-height set in zulip.css */
export const DEFAULT_DROPDOWN_HEIGHT = 210;
const noop = (): void => {
    // Empty function for default values.
};

export type DataType = "number" | "string";

export type Option = {
    unique_id: number | string;
    name: string;
    description?: string;
    is_direct_message?: boolean;
    is_setting_disabled?: boolean;
    stream?: StreamSubscription;
    bold_current_selection?: boolean;
    has_delete_icon?: boolean;
    has_edit_icon?: boolean;
};

export type DropdownWidgetOptions = {
    widget_name: string;
    widget_selector?: string;
    // You can bold the selected `option` by setting `option.bold_current_selection` to `true`.
    // Currently, not implemented for stream names.
    get_options: (current_value: string | number | undefined) => Option[];
    item_click_callback: (
        event: JQuery.ClickEvent,
        instance: tippy.Instance,
        widget: DropdownWidget,
        is_sticky_bottom_option_clicked: boolean,
    ) => void;
    // Provide an parent element to widget which will be re-rendered if the widget is setup again.
    // It is important to not pass `$("body")` here for widgets that would be `setup()`
    // multiple times, so that we don't have duplicate event handlers.
    $events_container: JQuery;
    on_show_callback?: (instance: tippy.Instance, widget: DropdownWidget) => void;
    on_mount_callback?: (instance: tippy.Instance) => void;
    on_hidden_callback?: (instance: tippy.Instance) => void;
    on_exit_with_escape_callback?: () => void;
    render_selected_option?: () => void;
    // Used to add a sticky button at the bottom of the dropdown.
    sticky_bottom_option?: string;
    // Used to focus the `target` after dropdown is closed. This is important since the dropdown is
    // appended to `body` and hence `body` is focused when the dropdown is closed, which makes
    // it hard for the user to get focus back to the `target`.
    focus_target_on_hidden?: boolean;
    tippy_props?: Partial<tippy.Props>;
    // NOTE: Any value other than `undefined` will be rendered when class is initialized.
    default_id?: string | number | undefined;
    unique_id_type?: DataType;
    // Text to show if the current value is not in `get_options()`.
    text_if_current_value_not_in_options?: string;
    hide_search_box?: boolean;
    // Disable the widget for spectators.
    disable_for_spectators?: boolean;
    dropdown_input_visible_selector?: string;
    prefer_top_start_placement?: boolean;
    // Boolean variable to check whether the dropdown is opened
    // with a keyboard trigger or not.
    dropdown_triggered_via_keyboard?: boolean;
    // When this is set, pressing tab will move focus to the target element.
    tab_moves_focus_to_target?: string | (() => string);
};

export class DropdownWidget {
    widget_name: string;
    widget_selector: string;
    widget_wrapper_id: string;
    widget_value_selector: string;
    get_options: (current_value: string | number | undefined) => Option[];
    item_click_callback: (
        event: JQuery.ClickEvent,
        instance: tippy.Instance,
        widget: DropdownWidget,
        is_sticky_bottom_option_clicked: boolean,
    ) => void;
    focus_target_on_hidden: boolean;
    on_show_callback: (instance: tippy.Instance, widget: DropdownWidget) => void;
    on_mount_callback: (instance: tippy.Instance) => void;
    on_hidden_callback: (instance: tippy.Instance) => void;
    on_exit_with_escape_callback: () => void;
    render_selected_option: () => void;
    sticky_bottom_option: string | undefined;
    tippy_props: Partial<tippy.Props>;
    list_widget: ListWidgetType<Option, Option> | undefined;
    instance: tippy.Instance | undefined;
    default_id: string | number | undefined;
    current_value: string | number | undefined;
    unique_id_type: DataType | undefined;
    $events_container: JQuery;
    text_if_current_value_not_in_options: string;
    hide_search_box: boolean;
    disable_for_spectators: boolean;
    dropdown_input_visible_selector: string;
    prefer_top_start_placement: boolean;
    dropdown_triggered_via_keyboard: boolean;
    keep_focus_on_search: boolean;
    tab_moves_focus_to_target: string | (() => string) | undefined;
    current_hover_index: number;

    // TODO: This is only used in one widget, with no implementation
    // here, so should be generalized or reworked.
    item_clicked = false;

    constructor(options: DropdownWidgetOptions) {
        this.widget_name = options.widget_name;
        this.widget_selector = options.widget_selector ?? `#${CSS.escape(this.widget_name)}_widget`;
        // A widget wrapper may not exist based on the UI requirement.
        this.widget_wrapper_id = `${this.widget_selector}_wrapper`;
        this.widget_value_selector = `${this.widget_selector} .dropdown_widget_value`;
        this.get_options = options.get_options;
        this.item_click_callback = options.item_click_callback;
        this.focus_target_on_hidden = options.focus_target_on_hidden ?? true;
        this.on_show_callback = options.on_show_callback ?? noop;
        this.on_mount_callback = options.on_mount_callback ?? noop;
        this.on_hidden_callback = options.on_hidden_callback ?? noop;
        this.on_exit_with_escape_callback = options.on_exit_with_escape_callback ?? noop;
        this.render_selected_option = options.render_selected_option ?? noop;
        this.sticky_bottom_option = options.sticky_bottom_option;
        // These properties can override any tippy props.
        this.tippy_props = options.tippy_props ?? {};
        this.list_widget = undefined;
        this.default_id = options.default_id;
        this.current_value = this.default_id;
        this.unique_id_type = options.unique_id_type;
        this.$events_container = options.$events_container;
        this.text_if_current_value_not_in_options =
            options.text_if_current_value_not_in_options ?? "";
        this.hide_search_box = options.hide_search_box ?? false;
        this.disable_for_spectators = options.disable_for_spectators ?? false;
        this.dropdown_input_visible_selector =
            options.dropdown_input_visible_selector ?? this.widget_selector;
        this.prefer_top_start_placement = options.prefer_top_start_placement ?? false;
        this.dropdown_triggered_via_keyboard = false;
        this.keep_focus_on_search = !this.hide_search_box;
        this.tab_moves_focus_to_target = options.tab_moves_focus_to_target;
        this.current_hover_index = 0;
    }

    init(): void {
        // NOTE: Widget should only be initialized again if the events_container was rendered again to
        // avoid duplicate events to be attached to events_container.
        // Don't attach any events or classes to any element other than `events_container` here, otherwise
        // the attached events / classes will be lost when the widget is rendered again without initialing the widget again.
        if (this.current_value !== undefined) {
            this.render();
        }

        this.$events_container.on(
            "keydown",
            `${this.widget_selector}, ${this.widget_wrapper_id}`,
            (e) => {
                if (e.key === "Enter") {
                    $(this.widget_selector)[0]?.click();
                    e.stopPropagation();
                    e.preventDefault();
                }
            },
        );

        if (this.disable_for_spectators && page_params.is_spectator) {
            this.$events_container.addClass("dropdown-widget-disabled-for-spectators");
            this.$events_container.on(
                "click",
                `${this.widget_selector}, ${this.widget_wrapper_id}`,
                (e) => {
                    e.stopPropagation();
                    e.preventDefault();
                },
            );
        }
    }

    adjust_dropdown_position_post_list_render(tippy_instance: tippy.Instance): void {
        let top_offset = 0;
        let left_offset = 0;

        // Use offset if provided by the widget callers.
        if (typeof this.tippy_props?.offset === "object" && this.tippy_props?.offset.length === 2) {
            left_offset = this.tippy_props.offset[0];
            top_offset = this.tippy_props.offset[1];
        }

        const window_height = window.innerHeight;
        let dropdown_search_box_and_padding_height = 50;
        if (this.hide_search_box) {
            dropdown_search_box_and_padding_height = 0;
        }
        const dropdown_input_props = $(this.dropdown_input_visible_selector).get_offset_to_window();
        const dropdown_input_top = dropdown_input_props.top;

        // Pixels above the dropdown input.
        const top_space = dropdown_input_top - top_offset - dropdown_search_box_and_padding_height;
        // Pixels below the top of dropdown input.
        const bottom_space =
            window_height - dropdown_input_top - dropdown_search_box_and_padding_height;

        // Show dropdown at bottom by default if we `DEFAULT_DROPDOWN_HEIGHT`
        // space available unless the dropdown caller prefers to show at top.
        // If we don't have `DEFAULT_DROPDOWN_HEIGHT` space available above
        // or below the dropdown input, show the dropdown at maximum space.
        let placement: tippy.Placement = "top-start";
        let height: number = Math.min(DEFAULT_DROPDOWN_HEIGHT, Math.max(top_space, bottom_space));
        if (this.prefer_top_start_placement && top_space > DEFAULT_DROPDOWN_HEIGHT) {
            height = DEFAULT_DROPDOWN_HEIGHT;
        } else if (!this.prefer_top_start_placement && bottom_space > DEFAULT_DROPDOWN_HEIGHT) {
            placement = "bottom-start";
            height = DEFAULT_DROPDOWN_HEIGHT;
            // Use the provided offset if we have enough space. Otherwise,
            // we overlap the top of dropdown with top of dropdown input.
            if (this.tippy_props?.offset === undefined) {
                top_offset = -1 * dropdown_input_props.height;
            }
        } else if (bottom_space > top_space) {
            placement = "bottom-start";
            top_offset = -1 * dropdown_input_props.height;
        }

        const offset: [number, number] = [left_offset, top_offset];
        tippy_instance.setProps({placement, offset});
        const $popper = $(tippy_instance.popper);
        $popper.find(".dropdown-list-wrapper").css("max-height", height + "px");
    }

    show_empty_if_no_items($popper: JQuery): void {
        assert(this.list_widget !== undefined);
        const list_items = this.list_widget.get_current_list();
        const $no_search_results = $popper.find(".no-dropdown-items");
        if (list_items.length === 0) {
            $no_search_results.show();
        } else {
            $no_search_results.hide();
        }
    }

    update_hover_state($popper: JQuery): void {
        assert(this.list_widget !== undefined);
        const list_items = this.list_widget.get_current_list();
        if (list_items.length === 0) {
            return;
        }
        $popper.find(".list-item.current_selection").removeClass("current_selection");
        if (this.sticky_bottom_option) {
            $popper
                .find(".sticky-bottom-option.current_selection")
                .removeClass("current_selection");
        }
        if (this.current_hover_index === list_items.length && this.sticky_bottom_option) {
            $popper.find(".sticky-bottom-option").addClass("current_selection");
        } else {
            const current_hover_item = list_items[this.current_hover_index];
            assert(current_hover_item !== undefined);
            const $item = $popper
                .find(`.list-item[data-unique-id="${current_hover_item.unique_id}"]`)
                .addClass("current_selection");
            if ($item.length === 0) {
                this.list_widget.render(this.current_hover_index + 1);
            }
            const element = $item[0];
            if (element) {
                element.scrollIntoView({block: "nearest"});
            }
        }
    }

    setup(): void {
        this.init();
        const delegate_container = util.the(this.$events_container);

        if (this.disable_for_spectators && page_params.is_spectator) {
            return;
        }

        // We want to prevent focus from moving to the list item
        // when it is clicked using a mouse.
        $(this.widget_selector).on("mousedown", () => {
            this.dropdown_triggered_via_keyboard = false;
        });

        $(this.widget_selector).on("keydown", () => {
            this.dropdown_triggered_via_keyboard = true;
        });

        tippy.delegate(delegate_container, {
            ...popover_menus.default_popover_props,
            target: this.widget_selector,
            // Custom theme defined in popovers.css
            theme: "dropdown-widget",
            arrow: false,
            onShow: (instance: tippy.Instance) => {
                if (util.is_mobile()) {
                    // The dropdown trigger button can be hidden by the
                    // keyboard on mobile or if it is scrolled out of
                    // view to keyboard being displayed.
                    // So, we show the dropdown even if reference is hidden on
                    // mobile.
                    $(instance.popper).find(".tippy-box").addClass("show-when-reference-hidden");
                }
                instance.setContent(
                    parse_html(
                        render_dropdown_list_container({
                            widget_name: this.widget_name,
                            hide_search_box: this.hide_search_box,
                            sticky_bottom_option: this.sticky_bottom_option,
                        }),
                    ),
                );
                const $popper = $(instance.popper);
                const $dropdown_list_body = $popper.find(".dropdown-list");
                const $search_input = $popper.find<HTMLInputElement>(
                    "input.dropdown-list-search-input",
                );
                const selected_item_unique_id = this.current_value;

                this.list_widget = ListWidget.create(
                    $dropdown_list_body,
                    this.get_options(this.current_value),
                    {
                        name: `${CSS.escape(this.widget_name)}-list-widget`,
                        get_item: ListWidget.default_get_item,
                        modifier_html(item) {
                            return render_dropdown_list({
                                item: {
                                    ...item,
                                    is_current_user_setting:
                                        item.unique_id === selected_item_unique_id,
                                },
                            });
                        },
                        filter: {
                            $element: $search_input,
                            predicate(item, value) {
                                return item.name.toLowerCase().includes(value);
                            },
                        },
                        $simplebar_container: $popper.find(".dropdown-list-wrapper"),
                    },
                );

                $search_input.on("input.list_widget_filter", () => {
                    this.show_empty_if_no_items($popper);
                    if (this.keep_focus_on_search) {
                        $search_input.trigger("focus");
                        this.current_hover_index = 0;
                        this.update_hover_state($popper);
                    }
                });

                // Keyboard handler
                $popper.on("keydown", (e) => {
                    function trigger_element_focus($element: JQuery): void {
                        e.preventDefault();
                        e.stopPropagation();
                        // When bringing a non-visible element into view, scroll as minimum as possible.
                        $element[0]?.scrollIntoView({block: "nearest"});
                        $element.trigger("focus");
                    }

                    const $search_input = $popper.find(".dropdown-list-search-input");
                    const $sticky_bottom_option = $popper.find(".sticky-bottom-option");
                    assert(this.list_widget !== undefined);
                    const list_items = this.list_widget.get_current_list();
                    if (
                        list_items.length === 0 &&
                        !(e.key === "Escape") &&
                        !this.sticky_bottom_option
                    ) {
                        // Let the browser handle it.
                        return;
                    }

                    function get_item_by_index(index: number): JQuery {
                        const item = list_items[index];
                        assert(item !== undefined);
                        return $popper.find(`.list-item[data-unique-id="${item.unique_id}"]`);
                    }

                    function first_item(): JQuery {
                        return get_item_by_index(0);
                    }

                    function last_item(): JQuery {
                        return get_item_by_index(list_items.length - 1);
                    }

                    const render_all_items = (): void => {
                        assert(this.list_widget !== undefined);
                        // List widget doesn't render all items by default, so we need to render all
                        // the items and focus on the last element.
                        const list_items = this.list_widget.get_current_list();
                        this.list_widget.render(list_items.length);
                    };

                    const handle_arrow_down_on_last_item = (): void => {
                        if (this.sticky_bottom_option) {
                            trigger_element_focus($sticky_bottom_option);
                        } else if (this.hide_search_box) {
                            trigger_element_focus(first_item());
                        } else {
                            trigger_element_focus($search_input);
                        }
                    };

                    const handle_arrow_down_on_sticky_bottom_option = (): void => {
                        if (this.hide_search_box) {
                            trigger_element_focus(first_item());
                        } else {
                            trigger_element_focus($search_input);
                        }
                    };

                    const handle_arrow_up_on_sticky_bottom_option = (): void => {
                        if (list_items.length > 0) {
                            render_all_items();
                            trigger_element_focus(last_item());
                        } else if (!this.hide_search_box) {
                            trigger_element_focus($search_input);
                        }
                    };

                    const handle_arrow_down_on_search_input = (): void => {
                        if (list_items.length > 0) {
                            trigger_element_focus(first_item());
                        } else if (this.sticky_bottom_option) {
                            trigger_element_focus($sticky_bottom_option);
                        }
                    };

                    const handle_arrow_down_on_sequential_focus = (): void => {
                        switch (e.target) {
                            case $search_input.get(0):
                                handle_arrow_down_on_search_input();
                                break;
                            case $sticky_bottom_option.get(0):
                                handle_arrow_down_on_sticky_bottom_option();
                                break;
                            case last_item().get(0):
                                handle_arrow_down_on_last_item();
                                break;
                            default:
                                trigger_element_focus($(e.target).next());
                        }
                    };

                    const handle_arrow_up_on_search_input = (): void => {
                        if (this.sticky_bottom_option) {
                            trigger_element_focus($sticky_bottom_option);
                        } else {
                            render_all_items();
                            trigger_element_focus(last_item());
                        }
                    };

                    const handle_arrow_up_on_first_item = (): void => {
                        if (this.hide_search_box) {
                            render_all_items();
                            trigger_element_focus(last_item());
                        } else {
                            trigger_element_focus($search_input);
                        }
                    };

                    const update_highlighted_index = (new_index: number): void => {
                        let length = list_items.length;
                        if (this.sticky_bottom_option) {
                            length += 1;
                        }
                        if (new_index >= length) {
                            this.current_hover_index = 0;
                        } else if (new_index < 0) {
                            render_all_items();
                            this.current_hover_index = length - 1;
                        } else {
                            this.current_hover_index = new_index;
                        }
                        this.update_hover_state($popper);
                    };

                    switch (e.key) {
                        case "Enter":
                            if (
                                list_items.length === 0 ||
                                e.target === $sticky_bottom_option.get(0)
                            ) {
                                $sticky_bottom_option.trigger("click");
                            } else if (e.target === $search_input.get(0)) {
                                if (this.keep_focus_on_search) {
                                    if (
                                        this.sticky_bottom_option &&
                                        list_items.length === this.current_hover_index
                                    ) {
                                        $sticky_bottom_option.trigger("click");
                                    } else {
                                        const $item = get_item_by_index(this.current_hover_index);
                                        $item.trigger("click");
                                    }
                                } else {
                                    // Select first item if in search input.
                                    first_item().trigger("click");
                                }
                            } else if (list_items.length > 0) {
                                $(e.target).trigger("click");
                            }
                            e.stopPropagation();
                            e.preventDefault();
                            break;

                        case "Escape":
                            popover_menus.hide_current_popover_if_visible(instance);
                            this.on_exit_with_escape_callback();
                            this.current_hover_index = 0;
                            e.stopPropagation();
                            e.preventDefault();
                            break;

                        case "Tab":
                            if (this.tab_moves_focus_to_target) {
                                e.preventDefault();
                                e.stopPropagation();
                                popover_menus.hide_current_popover_if_visible(instance);
                                this.current_hover_index = 0;
                                const target =
                                    typeof this.tab_moves_focus_to_target === "function"
                                        ? this.tab_moves_focus_to_target()
                                        : this.tab_moves_focus_to_target;
                                $(target).trigger("focus");
                            } else if (!this.hide_search_box && this.keep_focus_on_search) {
                                e.preventDefault();
                                e.stopPropagation();
                                update_highlighted_index(this.current_hover_index + 1);
                                break;
                            } else {
                                handle_arrow_down_on_sequential_focus();
                                break;
                            }
                    }

                    if (!this.hide_search_box && this.keep_focus_on_search) {
                        switch (e.key) {
                            case "ArrowDown":
                                e.preventDefault();
                                e.stopPropagation();
                                update_highlighted_index(this.current_hover_index + 1);
                                break;
                            case "ArrowUp":
                                e.preventDefault();
                                e.stopPropagation();
                                update_highlighted_index(this.current_hover_index - 1);
                                break;
                        }
                    } else {
                        switch (e.key) {
                            case "ArrowDown":
                                handle_arrow_down_on_sequential_focus();
                                break;

                            case "ArrowUp":
                                switch (e.target) {
                                    case $search_input.get(0):
                                        handle_arrow_up_on_search_input();
                                        break;
                                    case $sticky_bottom_option.get(0):
                                        handle_arrow_up_on_sticky_bottom_option();
                                        break;
                                    case first_item().get(0):
                                        handle_arrow_up_on_first_item();
                                        break;
                                    default:
                                        trigger_element_focus($(e.target).prev());
                                }
                                break;
                        }
                    }
                });

                // We want to prevent focus from moving to the list item
                // when it is clicked with a mouse. This is necessary because
                // it was reported that the blue focus outline briefly appears
                // when items are clicked, before the dropdown closes.
                $popper.on("mousedown", ".list-item", (event) => {
                    event.preventDefault();
                });

                // Click on item.
                $popper.on("click", ".list-item", (event) => {
                    event.preventDefault();
                    const selected_unique_id = $(event.currentTarget).attr("data-unique-id");
                    assert(selected_unique_id !== undefined);
                    this.current_value = selected_unique_id;
                    if (this.unique_id_type === "number") {
                        this.current_value = Number.parseInt(this.current_value, 10);
                    }
                    this.item_click_callback(event, instance, this, false);
                    this.current_hover_index = 0;
                });

                // Click on $sticky_bottom_option.
                $popper.on("click", ".sticky-bottom-option", (event) => {
                    this.item_click_callback(event, instance, this, true);
                    this.current_hover_index = 0;
                });

                // Adjust focus based on how the dropdown was opened
                setTimeout(() => {
                    if (this.hide_search_box) {
                        if (this.dropdown_triggered_via_keyboard) {
                            // IF the dropdown is opened by keyboard, focus on the first item.
                            const $selected_item = $dropdown_list_body.find(
                                `.list-item[data-unique-id="${this.current_value}"]`,
                            );
                            $selected_item.trigger("focus");
                        } else {
                            assert(this.list_widget !== undefined);
                            // Above, we avoided focusing on any item of the dropdown
                            // when it is opened by a mousedown event. However, as soon
                            // as the user presses ArrowUp or ArrowDown, we move the focus
                            // on the first item of the dropdown.
                            const first_item = this.list_widget.get_current_list()[0];
                            if (first_item) {
                                const $first_item = $popper.find(
                                    `.list-item[data-unique-id="${first_item.unique_id}"]`,
                                );
                                this.$events_container.one(
                                    "keydown",
                                    `${this.widget_selector}, ${this.widget_wrapper_id}`,
                                    (e) => {
                                        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                                            $first_item.trigger("focus");
                                            e.stopPropagation();
                                            e.preventDefault();
                                        }
                                    },
                                );
                            }
                        }
                    } else {
                        $search_input.trigger("focus");
                        if (this.keep_focus_on_search) {
                            this.current_hover_index = 0;
                            this.update_hover_state($popper);
                        }
                    }
                }, 0);

                this.on_show_callback(instance, this);
                this.adjust_dropdown_position_post_list_render(instance);
            },
            onMount: (instance: tippy.Instance) => {
                this.show_empty_if_no_items($(instance.popper));
                this.on_mount_callback(instance);
            },
            onHidden: (instance: tippy.Instance) => {
                if (this.focus_target_on_hidden) {
                    $(this.widget_selector).trigger("focus");
                }
                this.current_hover_index = 0;
                this.on_hidden_callback(instance);
                instance.destroy();
            },
            ...this.tippy_props,
        });
    }

    value(): number | string | undefined {
        return this.current_value;
    }

    // NOTE: This function needs to be explicitly called when you want to update the
    // current value of the widget. We don't call this automatically since some of our
    // dropdowns don't need it. Maybe we can follow a reverse approach in the future.
    render(value?: number | string): void {
        // Check if the value is valid otherwise just render previous value.
        if (value !== undefined && typeof value === typeof this.current_value) {
            this.current_value = value;
        }

        const all_options = this.get_options(this.current_value);
        const option = all_options.find((option) => option.unique_id === this.current_value);

        // If provided, show custom text if cannot find current option.
        if (!option && this.text_if_current_value_not_in_options) {
            $(this.widget_value_selector).html(
                render_dropdown_current_value_not_in_options({
                    name: this.text_if_current_value_not_in_options,
                }),
            );
            return;
        }

        if (!option) {
            blueslip.error(`Cannot find current value: ${this.current_value} in provided options.`);
            return;
        }

        if (option.is_setting_disabled) {
            $(this.widget_value_selector).html(render_dropdown_disabled_state({name: option.name}));
        } else if (option.stream) {
            $(this.widget_value_selector).html(
                render_inline_decorated_channel_name({
                    stream: option.stream,
                    show_colored_icon: true,
                }),
            );
        } else {
            $(this.widget_value_selector).text(option.name);
        }
    }
}
