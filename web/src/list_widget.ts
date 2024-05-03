import $ from "jquery";
import assert from "minimalistic-assert";

import render_empty_list_widget_for_list from "../templates/empty_list_widget_for_list.hbs";
import render_empty_list_widget_for_table from "../templates/empty_list_widget_for_table.hbs";

import * as blueslip from "./blueslip";
import * as scroll_util from "./scroll_util";

type SortingFunction<T> = (a: T, b: T) => number;

type ListWidgetMeta<Key, Item = Key> = {
    sorting_function: SortingFunction<Item> | null;
    sorting_functions: Map<string, SortingFunction<Item>>;
    filter_value: string;
    offset: number;
    list: Key[];
    filtered_list: Item[];
    reverse_mode: boolean;
    $scroll_container: JQuery;
};

// This type ensures the mutually exclusive nature of the predicate and filterer options.
type ListWidgetFilterOpts<Item> = {
    $element?: JQuery<HTMLInputElement>;
    onupdate?: () => void;
} & (
    | {
          predicate: (item: Item, value: string) => boolean;
          filterer?: never;
      }
    | {
          predicate?: never;
          filterer: (list: Item[], value: string) => Item[];
      }
);

type ListWidgetOpts<Key, Item = Key> = {
    name?: string;
    get_item: (key: Key) => Item;
    modifier_html: (item: Item, filter_value: string) => string;
    init_sort?: string | SortingFunction<Item>;
    initially_descending_sort?: boolean;
    html_selector?: (item: Item) => JQuery;
    callback_after_render?: () => void;
    post_scroll__pre_render_callback?: () => void;
    get_min_load_count?: (rendered_count: number, load_count: number) => number;
    is_scroll_position_for_render?: (scroll_container: HTMLElement) => boolean;
    filter?: ListWidgetFilterOpts<Item>;
    multiselect?: {
        selected_items: Key[];
    };
    sort_fields?: Record<string, SortingFunction<Item>>;
    $simplebar_container: JQuery;
    $parent_container?: JQuery;
};

type BaseListWidget = {
    clear_event_handlers: () => void;
};

export type ListWidget<Key, Item = Key> = BaseListWidget & {
    get_current_list: () => Item[];
    filter_and_sort: () => void;
    retain_selected_items: () => void;
    all_rendered: () => boolean;
    render: (how_many?: number) => void;
    render_item: (item: Item) => void;
    clear: () => void;
    set_filter_value: (value: string) => void;
    set_reverse_mode: (reverse_mode: boolean) => void;
    set_sorting_function: (sorting_function: string | SortingFunction<Item>) => void;
    set_up_event_handlers: () => void;
    increase_rendered_offset: () => void;
    reduce_rendered_offset: () => void;
    remove_rendered_row: (row: JQuery) => void;
    clean_redraw: () => void;
    hard_redraw: () => void;
    insert_rendered_row: (
        item: Item,
        get_insert_index: (list: Item[], item: Item) => number,
    ) => void;
    sort: (sorting_function: string, prop?: string) => void;
    replace_list_data: (list: Key[]) => void;
};

const DEFAULTS = {
    INITIAL_RENDER_COUNT: 80,
    LOAD_COUNT: 20,
    instances: new Map<string, BaseListWidget>(),
};

// ----------------------------------------------------
// This function describes (programmatically) how to use the ListWidget.
// ----------------------------------------------------

export function get_filtered_items<Key, Item>(
    value: string,
    list: Key[],
    opts: ListWidgetOpts<Key, Item>,
): Item[] {
    /*
        This is used by the main object (see `create`),
        but we split it out to make it a bit easier
        to test.
    */
    const get_item = opts.get_item;

    if (!opts.filter) {
        return list.map((key) => get_item(key));
    }

    if (opts.filter.filterer) {
        return opts.filter.filterer(
            list.map((key) => get_item(key)),
            value,
        );
    }

    const predicate = (item: Item): boolean => opts.filter!.predicate!(item, value);

    const result = [];

    for (const key of list) {
        const item = get_item(key);
        if (predicate(item)) {
            result.push(item);
        }
    }

    return result;
}

export function alphabetic_sort<Prop extends string>(
    prop: Prop,
): SortingFunction<Record<Prop, string>> {
    return (a, b) => {
        // The conversion to uppercase helps make the sorting case insensitive.
        const str1 = a[prop].toUpperCase();
        const str2 = b[prop].toUpperCase();

        if (str1 === str2) {
            return 0;
        } else if (str1 > str2) {
            return 1;
        }

        return -1;
    };
}

export function numeric_sort<Prop extends string>(
    prop: Prop,
): SortingFunction<Record<Prop, number>> {
    return (a, b) => {
        const a_prop = a[prop];
        const b_prop = b[prop];

        if (a_prop > b_prop) {
            return 1;
        } else if (a_prop === b_prop) {
            return 0;
        }

        return -1;
    };
}

type GenericSortKeys = {
    alphabetic: string;
    numeric: number;
};

const generic_sorts: {
    [GenericFunc in keyof GenericSortKeys]: <Prop extends string>(
        prop: Prop,
    ) => SortingFunction<Record<Prop, GenericSortKeys[GenericFunc]>>;
} = {
    alphabetic: alphabetic_sort,
    numeric: numeric_sort,
};

export function generic_sort_functions<
    GenericFunc extends keyof GenericSortKeys,
    Prop extends string,
>(
    generic_func: GenericFunc,
    props: Prop[],
): Record<string, SortingFunction<Record<Prop, GenericSortKeys[GenericFunc]>>> {
    return Object.fromEntries(
        props.map((prop) => [`${prop}_${generic_func}`, generic_sorts[generic_func](prop)]),
    );
}

function is_scroll_position_for_render(scroll_container: HTMLElement): boolean {
    return (
        scroll_container.scrollHeight -
            (scroll_container.scrollTop + scroll_container.clientHeight) <
        10
    );
}

function get_column_count_for_table($table: JQuery): number {
    let column_count = 0;
    const $thead = $table.find("thead");
    if ($thead.length) {
        column_count = $thead.find("tr").children().length;
    }
    return column_count;
}

export function render_empty_list_message_if_needed(
    $container: JQuery,
    filter_value: string,
): void {
    let empty_list_message = $container.attr("data-empty");

    const empty_search_results_message = $container.attr("data-search-results-empty");
    if (filter_value && empty_search_results_message) {
        empty_list_message = empty_search_results_message;
    }

    if (!empty_list_message || $container.children().length) {
        return;
    }

    let empty_list_widget_html;

    if ($container.is("table, tbody")) {
        let $table = $container;
        if ($container.is("tbody")) {
            $table = $container.closest("table");
        }

        const column_count = get_column_count_for_table($table);
        empty_list_widget_html = render_empty_list_widget_for_table({
            empty_list_message,
            column_count,
        });
    } else {
        empty_list_widget_html = render_empty_list_widget_for_list({
            empty_list_message,
        });
    }

    $container.append($(empty_list_widget_html));
}

// @params
// $container: jQuery object to append to.
// list: The list of items to progressively append.
// opts: An object of random preferences.
export function create<Key, Item = Key>(
    $container: JQuery,
    list: Key[],
    opts: ListWidgetOpts<Key, Item>,
): ListWidget<Key, Item> | undefined {
    if (opts.name && DEFAULTS.instances.get(opts.name)) {
        // Clear event handlers for prior widget.
        const old_widget = DEFAULTS.instances.get(opts.name)!;
        old_widget.clear_event_handlers();
    }

    const meta: ListWidgetMeta<Key, Item> = {
        sorting_function: null,
        sorting_functions: new Map(),
        offset: 0,
        list,
        filtered_list: [],
        reverse_mode: false,
        filter_value: "",
        $scroll_container: scroll_util.get_scroll_element(opts.$simplebar_container),
    };

    const widget: ListWidget<Key, Item> = {
        get_current_list() {
            return meta.filtered_list;
        },

        filter_and_sort() {
            meta.filtered_list = get_filtered_items(meta.filter_value, meta.list, opts);

            if (meta.sorting_function) {
                meta.filtered_list.sort(meta.sorting_function);
            }

            if (meta.reverse_mode) {
                meta.filtered_list.reverse();
            }
        },

        // Used in case of Multiselect DropdownListWidget to retain
        // previously checked items even after widget redraws.
        retain_selected_items() {
            const items = opts.multiselect;

            if (items?.selected_items) {
                const data = items.selected_items;
                for (const value of data) {
                    const $list_item = $container.find(
                        `li[data-value="${CSS.escape(String(value))}"]`,
                    );
                    if ($list_item.length) {
                        const $link_elem = $list_item.find("a").expectOne();
                        $list_item.addClass("checked");
                        $link_elem.prepend($("<i>").addClass(["fa", "fa-check"]));
                    }
                }
            }
        },

        // Returns if all available items are rendered.
        all_rendered() {
            return meta.offset >= meta.filtered_list.length;
        },

        // Reads the provided list (in the scope directly above)
        // and renders the next block of messages automatically
        // into the specified container.
        render(how_many) {
            let load_count = how_many ?? DEFAULTS.LOAD_COUNT;
            if (opts.get_min_load_count) {
                load_count = opts.get_min_load_count(meta.offset, load_count);
            }

            // Stop once the offset reaches the length of the original list.
            if (this.all_rendered()) {
                render_empty_list_message_if_needed($container, meta.filter_value);
                if (opts.callback_after_render) {
                    opts.callback_after_render();
                }
                return;
            }

            const slice = meta.filtered_list.slice(meta.offset, meta.offset + load_count);

            let html = "";
            for (const item of slice) {
                const item_html = opts.modifier_html(item, meta.filter_value);

                if (typeof item_html !== "string") {
                    blueslip.error("List item is not a string", {item_html});
                    continue;
                }

                // append the HTML or nothing if corrupt (null, undef, etc.).
                if (item_html) {
                    html += item_html;
                }
            }

            $container.append($(html));
            meta.offset += load_count;

            if (opts.multiselect) {
                widget.retain_selected_items();
            }

            if (opts.callback_after_render) {
                opts.callback_after_render();
            }
        },

        render_item(item) {
            if (!opts.html_selector) {
                // We don't have any way to find the existing item.
                return;
            }
            const $html_item = meta.$scroll_container.find(opts.html_selector(item));
            if ($html_item.length === 0) {
                // We don't have the item in the current scroll container; it'll be
                // rendered with updated data when it is scrolled to.
                return;
            }

            const html = opts.modifier_html(item, meta.filter_value);
            if (typeof html !== "string") {
                blueslip.error("List item is not a string", {item: html});
                return;
            }

            // At this point, we have asserted we have all the information to replace
            // the html now.
            $html_item.replaceWith($(html));
        },

        clear() {
            $container.empty();
            meta.offset = 0;
        },

        set_filter_value(filter_value) {
            meta.filter_value = filter_value;
        },

        set_reverse_mode(reverse_mode) {
            meta.reverse_mode = reverse_mode;
        },

        // the sorting function is either the function or a string which will be a key
        // for the sorting_functions map to get the function. In case of generic sort
        // functions like numeric and alphabetic, we pass the string in the given format -
        // "{property}_{numeric|alphabetic}" - e.g. "email_alphabetic" or "age_numeric".
        set_sorting_function(sorting_function) {
            if (typeof sorting_function === "function") {
                meta.sorting_function = sorting_function;
            } else if (typeof sorting_function === "string") {
                if (!meta.sorting_functions.has(sorting_function)) {
                    blueslip.error("Sorting function not found: " + sorting_function);
                    return;
                }

                meta.sorting_function = meta.sorting_functions.get(sorting_function)!;
            }
        },

        set_up_event_handlers() {
            // on scroll of the nearest scrolling container, if it hits the bottom
            // of the container then fetch a new block of items and render them.
            meta.$scroll_container.on("scroll.list_widget_container", function () {
                if (opts.post_scroll__pre_render_callback) {
                    opts.post_scroll__pre_render_callback();
                }

                if (opts.is_scroll_position_for_render === undefined) {
                    opts.is_scroll_position_for_render = is_scroll_position_for_render;
                }

                const should_render = opts.is_scroll_position_for_render(this);
                if (should_render) {
                    widget.render();
                }
            });

            if (opts.$parent_container) {
                opts.$parent_container.on(
                    "click.list_widget_sort",
                    "[data-sort]",
                    function (this: HTMLElement) {
                        handle_sort($(this), widget);
                    },
                );
            }

            opts.filter?.$element?.on("input.list_widget_filter", function () {
                const value = this.value.toLocaleLowerCase();
                widget.set_filter_value(value);
                widget.hard_redraw();
            });
        },

        clear_event_handlers() {
            meta.$scroll_container.off("scroll.list_widget_container");

            if (opts.$parent_container) {
                opts.$parent_container.off("click.list_widget_sort", "[data-sort]");
            }

            opts.filter?.$element?.off("input.list_widget_filter");
        },

        increase_rendered_offset() {
            meta.offset = Math.min(meta.offset + 1, meta.filtered_list.length);
        },

        reduce_rendered_offset() {
            meta.offset = Math.max(meta.offset - 1, 0);
        },

        remove_rendered_row(rendered_row) {
            rendered_row.remove();
            // We removed a rendered row, so we need to reduce one offset.
            widget.reduce_rendered_offset();
        },

        clean_redraw() {
            widget.filter_and_sort();
            widget.clear();
            widget.render(DEFAULTS.INITIAL_RENDER_COUNT);
        },

        hard_redraw() {
            widget.clean_redraw();
            if (opts.filter?.onupdate) {
                opts.filter.onupdate();
            }
        },

        insert_rendered_row(item, get_insert_index) {
            // NOTE: Caller should call `filter_and_sort` before calling this function
            // so that `meta.filtered_list` already has the `item`.
            if (meta.filtered_list.length <= 2) {
                // Avoids edge cases for us and could be faster too.
                widget.clean_redraw();
                return;
            }

            assert(
                opts.filter?.predicate,
                "filter.predicate should be defined for insert_rendered_row",
            );
            if (!opts.filter.predicate(item, meta.filter_value)) {
                return;
            }

            // We need to insert the row for it to be displayed at the
            // correct position. filtered_list must contain the new item
            // since we know it is not hidden from the above check.
            const insert_index = get_insert_index(meta.filtered_list, item);

            // Rows greater than `offset` are not rendered in the DOM by list_widget;
            // for those, there's nothing to update.
            if (insert_index <= meta.offset) {
                if (!opts.html_selector) {
                    blueslip.error(
                        "Please specify modifier and html_selector when creating the widget.",
                    );
                }
                const rendered_row = opts.modifier_html(item, meta.filter_value);
                if (insert_index === meta.filtered_list.length - 1) {
                    const $target_row = opts.html_selector!(meta.filtered_list[insert_index - 1]);
                    $target_row.after($(rendered_row));
                } else {
                    const $target_row = opts.html_selector!(meta.filtered_list[insert_index + 1]);
                    $target_row.before($(rendered_row));
                }
                widget.increase_rendered_offset();
            }
        },

        sort(sorting_function, prop) {
            const key = prop ? `${prop}_${sorting_function}` : sorting_function;
            widget.set_sorting_function(key);
            widget.hard_redraw();
        },

        replace_list_data(list) {
            /*
                We mostly use this widget for lists where you are
                not adding or removing rows, so when you do modify
                the list, we have a brute force solution.
            */
            meta.list = list;
            widget.hard_redraw();
        },
    };

    widget.set_up_event_handlers();

    if (opts.sort_fields) {
        for (const [name, sorting_function] of Object.entries(opts.sort_fields)) {
            meta.sorting_functions.set(name, sorting_function);
        }
    }

    if (opts.init_sort) {
        widget.set_sorting_function(opts.init_sort);
    }

    if (opts.initially_descending_sort) {
        widget.set_reverse_mode(true);
        opts.$simplebar_container.find(".active").addClass("descend");
    }

    widget.clean_redraw();

    // Save the instance for potential future retrieval if a name is provided.
    if (opts.name) {
        DEFAULTS.instances.set(opts.name, widget);
    }

    return widget;
}

export function handle_sort<Key, Item>($th: JQuery, list: ListWidget<Key, Item>): void {
    /*
        one would specify sort parameters like this:
            - name => sort alphabetic.
            - age  => sort numeric.
            - status => look up `status` in sort_fields
                        to find custom sort function

        <thead>
            <th data-sort="alphabetic" data-sort-prop="name"></th>
            <th data-sort="numeric" data-sort-prop="age"></th>
            <th data-sort="status"></th>
        </thead>
        */
    const sort_type = $th.attr("data-sort");
    const prop_name = $th.attr("data-sort-prop");
    assert(sort_type !== undefined);

    if ($th.hasClass("active")) {
        if (!$th.hasClass("descend")) {
            $th.addClass("descend");
        } else {
            $th.removeClass("descend");
        }
    } else {
        $th.siblings(".active").removeClass("active");
        $th.addClass("active");
    }

    list.set_reverse_mode($th.hasClass("descend"));

    // if `prop_name` is defined, it will trigger the generic sort functions,
    // and not if it is undefined.
    list.sort(sort_type, prop_name);
}

export const default_get_item = <T>(item: T): T => item;
