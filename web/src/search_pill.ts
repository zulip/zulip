import {Filter} from "./filter";
import type {InputPillContainer, InputPillItem} from "./input_pill";
import * as input_pill from "./input_pill";

type SearchPill = {
    description_html : string;
};
export type SearchPillWidget = InputPillContainer<SearchPill>;

export function create_item_from_search_string(search_string : string) : InputPillItem<SearchPill>{
    const operator = Filter.parse(search_string);
    const description_html = Filter.search_description_as_html(operator);
    return {
        type: "search",
        display_value: search_string,
        description_html,
    };
}

export function get_search_string_from_item(item: InputPillItem<SearchPill>) : string {
    return item.display_value;
}

export function create_pills($pill_container: JQuery) : input_pill.InputPillContainer<SearchPill> {
    const pills = input_pill.create({
        $container: $pill_container,
        create_item_from_text: create_item_from_search_string,
        get_text_from_item: get_search_string_from_item,
    });
    return pills;
}

export function append_search_string(search_string : string, pill_widget : SearchPillWidget) : void {
    const items = pill_widget.items();
    const search_strings = new Set(items.map((item) => item.display_value));

    const operators = Filter.parse(search_string);
    for (const operator of operators) {
        const input = Filter.unparse([operator]);
        if (!search_strings.has(input)) {
            pill_widget.appendValue(input);
        }
    }
    pill_widget.clear_text();
}

export function get_search_string_for_current_filter(pill_widget : SearchPillWidget) : string {
    const items = pill_widget.items();
    const search_strings = items.map((item) => item.display_value);
    return search_strings.join(" ");
}
