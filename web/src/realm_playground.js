import generated_pygments_data from "../generated/pygments_data.json";
import * as typeahead from "../shared/src/typeahead";

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
        typeahead_helper.compare_language,
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

// This gets the candidate list for showing autocomplete for a code block in
// the composebox. The candidate list will include pygments data as well as any
// Code Playgrounds.
//
// May return duplicates, since it's common for playground languages
// to also be pygments languages! retain_unique_language_aliases will
// deduplicate them.
export function get_pygments_typeahead_list_for_composebox() {
    const playground_pygment_langs = [...map_language_to_playground_info.keys()];
    const generated_pygment_langs = Object.keys(generated_pygments_data.langs);

    return [...playground_pygment_langs, ...generated_pygment_langs];
}

// This gets the candidate list for showing autocomplete in settings when
// adding a new Code Playground.
export function get_pygments_typeahead_list_for_settings(query) {
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

    const playground_pygment_langs = [...map_language_to_playground_info.keys()];
    for (const lang of playground_pygment_langs) {
        language_labels.set(lang, $t({defaultMessage: "Custom language: {query}"}, {query: lang}));
    }

    for (const [key, values] of map_pygments_pretty_name_to_aliases) {
        language_labels.set(key, key + " (" + values.join(", ") + ")");
    }

    return language_labels;
}

export function initialize(playground_data, generated_pygments_data) {
    update_playgrounds(playground_data);
    sort_pygments_pretty_names_by_priority(generated_pygments_data);
}
