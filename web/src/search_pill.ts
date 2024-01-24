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

export function append_search_string(
    search_string: string,
    pill_widget: SearchPillWidget,
    set_search_bar_text?: (text: string) => void,
): void {
    const terms = Filter.parse(search_string);
    let partial_pill = "";
    for (const term of terms) {
        const input = Filter.unparse([term]);
        // If the last term looks something like `dm:`, we
        // don't want to make it a pill, since it isn't isn't
        // a complete search term yet.
        // Instead, we keep the partial pill to the end of the
        // search box as text input, which will update the
        // typeahead to show operand suggestions.
        if (set_search_bar_text !== undefined && input.at(-1) === ":" && term === terms.at(-1)) {
            partial_pill = input;
            continue;
        }
        pill_widget.appendValue(input);
    }
    pill_widget.clear_text();
    if (set_search_bar_text !== undefined) {
        set_search_bar_text(partial_pill);
    }
}

export function get_current_search_string_for_widget(pill_widget: SearchPillWidget): string {
    const items = pill_widget.items();
    const search_strings = items.map((item) => item.display_value);
    return search_strings.join(" ");
}
