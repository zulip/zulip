import * as blueslip from "./blueslip";
import * as markdown from "./markdown";

const linkifier_map = new Map(); // regex -> url

export function get_linkifier_map() {
    return linkifier_map;
}

function python_to_js_linkifier(pattern, url) {
    // Converts a python named-group regex to a javascript-compatible numbered
    // group regex... with a regex!
    const named_group_re = /\(?P<([^>]+?)>/g;
    let match = named_group_re.exec(pattern);
    let current_group = 1;
    while (match) {
        const name = match[1];
        // Replace named group with regular matching group
        pattern = pattern.replace("(?P<" + name + ">", "(");
        // Replace named reference in URL to numbered reference
        url = url.replace("%(" + name + ")s", "\\" + current_group);

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
        const py_flags = match[1].split("");

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
        blueslip.error("python_to_js_linkifier: " + error.message);
    }
    return [final_regex, url];
}

export function update_linkifier_rules(linkifiers) {
    linkifier_map.clear();

    for (const linkifier of linkifiers) {
        const [regex, final_url] = python_to_js_linkifier(linkifier.pattern, linkifier.url_format);
        if (!regex) {
            // Skip any linkifiers that could not be converted
            continue;
        }

        linkifier_map.set(regex, final_url);
    }

    // Update our parser with our particular set of linkifiers.
    markdown.set_linkifier_regexes(Array.from(linkifier_map.keys()));
}

export function initialize(linkifiers) {
    update_linkifier_rules(linkifiers);
}
