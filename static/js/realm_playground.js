import * as typeahead_helper from "./typeahead_helper";

const map_language_to_playground_info = new Map();
const pygments_pretty_name_list = new Set();

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
    for (const data of priority_sorted_pygments_data) {
        const pretty_name = generated_pygments_data.langs[data].pretty_name;
        // JS maintains the order of insertion in a set so we don't need to worry about
        // the priority changing.
        if (!pygments_pretty_name_list.has(pretty_name)) {
            pygments_pretty_name_list.add(pretty_name);
        }
    }
}

export function get_pygments_pretty_names_list() {
    return Array.from(pygments_pretty_name_list);
}

export function initialize(playground_data, generated_pygments_data) {
    update_playgrounds(playground_data);
    sort_pygments_pretty_names_by_priority(generated_pygments_data);
}
