"use strict";

const {createIntl, createIntlCache} = require("@formatjs/intl");
const _ = require("lodash");

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

exports.$t_html = (descriptor, values) => {
    descriptor = {
        id: `${descriptor.defaultMessage}#${descriptor.description}`,
        ...descriptor,
    };
    return (
        "translated HTML: " +
        exports.intl.formatMessage(descriptor, {
            ...default_html_elements,
            ...Object.fromEntries(
                Object.entries(values ?? {}).map(([key, value]) => [
                    key,
                    typeof value === "function" ? value : _.escape(value),
                ]),
            ),
        })
    );
};
