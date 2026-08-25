import {RE2JS} from "re2js";
import Template from "uri-template-lite";
import type * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import type {realm_linkifier_schema} from "./state_data.ts";

export type LinkifierMapValue = {
    url_template: Template;
    reverse_template: string | null;
    alternative_url_templates: Template[];
};

type LinkifierMap = Map<RE2JS, LinkifierMapValue>;
const linkifier_map: LinkifierMap = new Map();

type Linkifier = z.output<typeof realm_linkifier_schema>;

export function get_linkifier_map(): LinkifierMap {
    return linkifier_map;
}

export function compile_linkifier(pattern: string, url: string): [RE2JS, Template] {
    // This boundary-matching must be kept in sync with prepare_linkifier_pattern
    // in zerver/lib/markdown/__init__.py.  It does not use look-ahead or
    // look-behind, because re2 does not support either.
    // RE2 uses \x{NNNN} for Unicode escapes, not \uNNNN.
    pattern = "(^|\\s|\\x{0085}|\\pZ|['\"(,:<])(" + pattern + ")($|[^\\pL\\pN])";
    const compiled_regex = RE2JS.compile(pattern);
    const url_template = new Template(url);
    return [compiled_regex, url_template];
}

export function update_linkifier_rules(linkifiers: Linkifier[]): void {
    linkifier_map.clear();

    for (const linkifier of linkifiers) {
        try {
            const [regex, url_template] = compile_linkifier(
                linkifier.pattern,
                linkifier.url_template,
            );
            const alternative_url_templates = (linkifier.alternative_url_templates ?? []).map(
                (template_string) => new Template(template_string),
            );
            linkifier_map.set(regex, {
                url_template,
                reverse_template: linkifier.reverse_template ?? null,
                alternative_url_templates,
            });
        } catch (error) {
            // We have an error computing the generated regex syntax.
            // We'll ignore this linkifier for now, but log this
            // failure for debugging later.
            blueslip.error("Failed to compile linkifier!", linkifier, error);
        }
    }
}

export function initialize(linkifiers: Linkifier[]): void {
    update_linkifier_rules(linkifiers);
}
