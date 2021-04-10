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
                (content_html) => `<${tag}>${content_html}</${tag}>`,
            ]),
        ),
    },
    cache,
);

exports.$t = (descriptor, values) =>
    "translated: " +
    exports.intl.formatMessage(
        {
            ...descriptor,
            id: `${descriptor.defaultMessage}#${descriptor.description}`,
        },
        values,
    );

const default_html_elements = Object.fromEntries(
    ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
        tag,
        (content_html) => `<${tag}>${content_html}</${tag}>`,
    ]),
);

exports.$t_html = (descriptor, values) =>
    "translated HTML: " +
    exports.intl.formatMessage(
        {
            ...descriptor,
            id: `${descriptor.defaultMessage}#${descriptor.description}`,
        },
        {
            ...default_html_elements,
            ...Object.fromEntries(
                Object.entries(values ?? {}).map(([key, value]) => [
                    key,
                    typeof value === "function" ? value : _.escape(value),
                ]),
            ),
        },
    );

exports.i18n = {};
exports.i18n.t = function (str, context) {
    // HAPPY PATH: most translations are a simple string:
    if (context === undefined) {
        return "translated: " + str;
    }

    /*
    context will be an ordinary JS object like this:

        {minutes: minutes.toString()}

    This supports use cases like the following:

        i18n.t("__minutes__ min to edit", {minutes: minutes.toString()})

    We have to munge in the context here.
    */
    const keyword_regex = /__(- )?(\w)+__/g;
    const keys_in_str = str.match(keyword_regex) || [];
    const substitutions = keys_in_str.map((key) => {
        let prefix_length;
        if (key.startsWith("__- ")) {
            prefix_length = 4;
        } else {
            prefix_length = 2;
        }
        return {
            keyword: key.slice(prefix_length, -2),
            prefix: key.slice(0, prefix_length),
            suffix: key.slice(-2, key.length),
        };
    });

    for (const item of substitutions) {
        str = str.replace(item.prefix + item.keyword + item.suffix, context[item.keyword]);
    }

    return "translated: " + str;
};
