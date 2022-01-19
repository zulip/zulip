import * as typeahead from "../shared/js/typeahead";

import {$t} from "./i18n";
import * as typeahead_helper from "./typeahead_helper";

const map_language_to_playground_info = new Map();
const map_pygments_pretty_name_to_aliases = new Map();

export function update_playgrounds(playgrounds_data) {
    map_language_to_playground_info.clear();

    for (const data of Object.values(playgrounds_data)) {
        const element_to_push = {
            id: data.id,
            name: data.name,
            url_prefix: data.url_prefix,
        };
        if (map_language_to_playground_info.has(data.pygments_language)) {
            map_language_to_playground_info.get(data.pygments_language).push(element_to_push);
        } else {
            map_language_to_playground_info.set(data.pygments_language, [element_to_push]);
        }
    }
}

export function get_playground_info_for_languages(lang) {
    return map_language_to_playground_info.get(lang);
}

export function sort_pygments_pretty_names_by_priority(generated_pygments_data) {
    const priority_sorted_pygments_data = Object.keys(generated_pygments_data.langs).sort(
        typeahead_helper.compare_by_popularity,
    );
    for (const alias of priority_sorted_pygments_data) {
        const pretty_name = generated_pygments_data.langs[alias].pretty_name;
        // JS Map remembers the original order of insertion of keys.
        if (map_pygments_pretty_name_to_aliases.has(pretty_name)) {
            map_pygments_pretty_name_to_aliases.get(pretty_name).push(alias);
        } else {
            map_pygments_pretty_name_to_aliases.set(pretty_name, [alias]);
        }
    }
}

export function get_pygments_typeahead_list(query) {
    const language_labels = new Map();

    // Adds a typeahead that allows selecting a custom language, by adding a
    // "Custom language" label in the first position of the typeahead list.
    const clean_query = typeahead.clean_query_lowercase(query);
    if (clean_query !== "") {
        language_labels.set(
            clean_query,
            $t({defaultMessage: "Custom language: {query}"}, {query: clean_query}),
        );
    }

    for (const [key, values] of map_pygments_pretty_name_to_aliases) {
        language_labels.set(key, key + " (" + Array.from(values).join(", ") + ")");
    }

    return language_labels;
}

export function initialize(playground_data, generated_pygments_data) {
    update_playgrounds(playground_data);
    sort_pygments_pretty_names_by_priority(generated_pygments_data);
}
