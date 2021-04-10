// For documentation on i18n in Zulip, see:
// https://zulip.readthedocs.io/en/latest/translating/internationalization.html

import {createIntl, createIntlCache} from "@formatjs/intl";
import i18next from "i18next";
import _ from "lodash";

import {page_params} from "./page_params";

const cache = createIntlCache();
export const intl = createIntl(
    {
        locale: page_params.default_language,
        defaultLocale: "en",
        messages: page_params.translation_data,
    },
    cache,
);

export const $t = intl.formatMessage;

export const default_html_elements = Object.fromEntries(
    ["b", "code", "em", "i", "kbd", "p", "strong"].map((tag) => [
        tag,
        (content_html) => `<${tag}>${content_html}</${tag}>`,
    ]),
);

export function $t_html(descriptor, values) {
    return intl.formatMessage(descriptor, {
        ...default_html_elements,
        ...Object.fromEntries(
            Object.entries(values ?? {}).map(([key, value]) => [
                key,
                typeof value === "function" ? value : _.escape(value),
            ]),
        ),
    });
}

i18next.init({
    lng: "lang",
    resources: {
        lang: {
            translation: page_params.translation_data,
        },
    },
    nsSeparator: false,
    keySeparator: false,
    interpolation: {
        prefix: "__",
        suffix: "__",
    },
    returnEmptyString: false, // Empty string is not a valid translation.
});

export const i18n = i18next;
