import url_template_lib from "url-template";

import * as blueslip from "./blueslip";

type LinkifierMap = Map<
    RegExp,
    {url_template: url_template_lib.Template; group_number_to_name: Record<number, string>}
>;
const linkifier_map: LinkifierMap = new Map();

type Linkifier = {
    pattern: string;
    url_template: string;
    id: number;
};

export function get_linkifier_map(): LinkifierMap {
    return linkifier_map;
}

function python_to_js_linkifier(
    pattern: string,
    url: string,
): [RegExp | null, url_template_lib.Template, Record<number, string>] {
    // Converts a python named-group regex to a javascript-compatible numbered
    // group regex... with a regex!
    const named_group_re = /\(?P<([^>]+?)>/g;
    let match = named_group_re.exec(pattern);
    let current_group = 1;
    const group_number_to_name: Record<number, string> = {};
    while (match) {
        const name = match[1];
        // Replace named group with regular matching group
        pattern = pattern.replace("(?P<" + name + ">", "(");
        // Map numbered reference to named reference for template expansion
        group_number_to_name[current_group] = name;

        // Reset the RegExp state
        named_group_re.lastIndex = 0;
        match = named_group_re.exec(pattern);

        current_group += 1;
    }
    // Convert any python in-regex flags to RegExp flags
    let js_flags = "g";
    const inline_flag_re = /\(\?([Limsux]+)\)/;
    match = inline_flag_re.exec(pattern);

    // JS regexes only support i (case insensitivity) and m (multiline)
    // flags, so keep those and ignore the rest
    if (match) {
        const py_flags = match[1];

        for (const flag of py_flags) {
            if ("im".includes(flag)) {
                js_flags += flag;
            }
        }

        pattern = pattern.replace(inline_flag_re, "");
    }
    // Ideally we should have been checking that linkifiers
    // begin with certain characters but since there is no
    // support for negative lookbehind in javascript, we check
    // for this condition in `contains_backend_only_syntax()`
    // function. If the condition is satisfied then the message
    // is rendered locally, otherwise, we return false there and
    // message is rendered on the backend which has proper support
    // for negative lookbehind.
    pattern = pattern + /(?!\w)/.source;
    let final_regex = null;
    try {
        final_regex = new RegExp(pattern, js_flags);
    } catch (error) {
        // We have an error computing the generated regex syntax.
        // We'll ignore this linkifier for now, but log this
        // failure for debugging later.
        if (error instanceof SyntaxError) {
            blueslip.error("python_to_js_linkifier failure!", {pattern}, error);
        } else {
            // Don't swallow any other (unexpected) exceptions.
            /* istanbul ignore next */
            throw error;
        }
    }
    const url_template = url_template_lib.parse(url);
    return [final_regex, url_template, group_number_to_name];
}

export function update_linkifier_rules(linkifiers: Linkifier[]): void {
    linkifier_map.clear();

    for (const linkifier of linkifiers) {
        const [regex, url_template, group_number_to_name] = python_to_js_linkifier(
            linkifier.pattern,
            linkifier.url_template,
        );
        if (!regex) {
            // Skip any linkifiers that could not be converted
            continue;
        }

        linkifier_map.set(regex, {
            url_template,
            group_number_to_name,
        });
    }
}

export function initialize(linkifiers: Linkifier[]): void {
    update_linkifier_rules(linkifiers);
}
