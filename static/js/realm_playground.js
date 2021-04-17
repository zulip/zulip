const map_language_to_playground_info = new Map();

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

export function initialize(playground_data) {
    update_playgrounds(playground_data);
}
