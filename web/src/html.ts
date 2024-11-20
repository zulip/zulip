import type Handlebars from "handlebars/runtime.js";
import {escape} from "lodash";

/**
 * An object wrapping an HTML string to mark that it has been safely generated
 * and should not be further escaped. Do not set the `__html` property using
 * untrusted input; use an `` html`…` `` tagged template literal instead.
 */
export type Html = {__html: string};

/**
 * A value that can be interpolated into an `` html`…` `` tagged template
 * literal.
 */
export type ToHtml =
    | undefined
    | null
    | boolean
    | string
    | number
    | Html
    | Handlebars.SafeString
    | readonly ToHtml[];

/**
 * Converts a value to an HTML string. Values that aren't `Html` objects will be
 * HTML-escaped; `undefined` and `null` will be treated as empty.
 *
 * @param value - The value to be converted
 * @returns An HTML string
 */
export function to_html(value: ToHtml): string {
    switch (typeof value) {
        case "string":
            return escape(value);
        case "number":
        case "boolean":
            return `${value}`;
        case "object":
            if (value === null) {
                return "";
            } else if ("__html" in value) {
                return value.__html;
            } else if ("toHTML" in value) {
                return value.toHTML();
            }
            return value.map((item) => to_html(item)).join("");
        default:
            return "";
    }
}

/**
 * A tag function to be used in a tagged template literal that builds an `Html`
 * object. Substitution values that aren't themselves `Html` objects will be
 * HTML-escaped; `undefined` and `null` will be treated as empty.
 *
 * @param template - The HTML into which values are interpolated
 * @param values - Substitution values
 * @returns An `Html` object
 *
 * @example
 * ```
 * const greeting = html`<div>Hello, ${name}!</div>`;
 * ```
 */
export function html(template: TemplateStringsArray, ...values: ToHtml[]): Html {
    const html_parts = values.flatMap((value, index) => [template[index], to_html(value)]);
    html_parts.push(template[values.length]);
    return {__html: html_parts.join("")};
}

/**
 * Join an array of values into an `Html` object, separated by the specified
 * separator. Values that aren't themselves `Html` objects will be HTML-escaped;
 * `undefined` and `null` will be treated as empty.
 *
 * @param values - Array of values to join
 * @param separator - Separator to insert between each value
 * @returns An `Html` object
 */
export function htmlJoin(values: ToHtml[], separator?: ToHtml): Html {
    return {__html: values.map((value) => to_html(value)).join(to_html(separator))};
}
