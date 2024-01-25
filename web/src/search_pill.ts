import {Filter} from "./filter";
import * as input_pill from "./input_pill";
import type {InputPillContainer} from "./input_pill";

type SearchPill = {
    display_value: string;
    type: string;
    description_html: string;
};
type SearchPillWidget = InputPillContainer<SearchPill>;

export function create_item_from_search_string(search_string: string): SearchPill {
    const operator = Filter.parse(search_string);
    const description_html = Filter.search_description_as_html(operator);
    return {
        display_value: search_string,
        type: "search",
        description_html,
    };
}

export function get_search_string_from_item(item: SearchPill): string {
    return item.display_value;
}

export function create_pills($pill_container: JQuery): SearchPillWidget {
    const pills = input_pill.create({
        $container: $pill_container,
        create_item_from_text: create_item_from_search_string,
        get_text_from_item: get_search_string_from_item,
    });
    return pills;
}

export function append_search_string(search_string: string, pill_widget: SearchPillWidget): void {
    const terms = Filter.parse(search_string);
    for (const term of terms) {
        const input = Filter.unparse([term]);
        pill_widget.appendValue(input);
    }
    pill_widget.clear_text();
}

export function get_current_search_string_for_widget(pill_widget: SearchPillWidget): string {
    const items = pill_widget.items();
    const search_strings = items.map((item) => item.display_value);
    return search_strings.join(" ");
}
