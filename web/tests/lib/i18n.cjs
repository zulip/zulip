"use strict";

const {createIntl, createIntlCache} = require("@formatjs/intl");
const {escape} = require("lodash");

const cache = createIntlCache();

exports.intl = createIntl(
    {
        locale: "en",
        defaultLocale: "en",
        defaultRichTextElements: Object.fromEntries(
            ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
                tag,
                /* istanbul ignore next */
                (content_html) => `<${tag}>${content_html.join("")}</${tag}>`,
            ]),
        ),
    },
    cache,
);

exports.$t = (descriptor, values) => {
    descriptor = {
        id: `${descriptor.defaultMessage}#${descriptor.description}`,
        ...descriptor,
    };
    return "translated: " + exports.intl.formatMessage(descriptor, values);
};

const default_html_elements = Object.fromEntries(
    ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
        tag,
        (content_html) => `<${tag}>${content_html.join("")}</${tag}>`,
    ]),
);

function to_html(value) {
    switch (typeof value) {
        case "string":
            return escape(value);
        case "number":
            return `${value}`;
        case "object":
            if (value === null) {
                return "";
            } else if ("__html" in value) {
                return value.__html;
            }
            return value.map((item) => to_html(item)).join("");
        default:
            return "";
    }
}

exports.$t_html = (descriptor, values = {}) => {
    descriptor = {
        id: `${descriptor.defaultMessage}#${descriptor.description}`,
        ...descriptor,
    };
    return (
        "translated HTML: " +
        exports.intl.formatMessage(descriptor, {
            ...default_html_elements,
            ...Object.fromEntries(
                Object.entries(values).map(([key, value]) => [
                    key,
                    typeof value === "function"
                        ? (content_html) => to_html(value({__html: content_html.join("")}))
                        : to_html(value),
                ]),
            ),
        })
    );
};
