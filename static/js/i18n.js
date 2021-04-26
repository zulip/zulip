// For documentation on i18n in Zulip, see:
// https://zulip.readthedocs.io/en/latest/translating/internationalization.html

import {DEFAULT_INTL_CONFIG, IntlErrorCode, createIntl, createIntlCache} from "@formatjs/intl";
import _ from "lodash";

import {page_params} from "./page_params";

const cache = createIntlCache();
export const intl = createIntl(
    {
        locale: page_params.request_language,
        defaultLocale: "en",
        messages: page_params.translation_data,
        onError: /* istanbul ignore next */ (error) => {
            // Ignore complaints about untranslated strings that were
            // added since the last sync-translations run.
            if (error.code !== IntlErrorCode.MISSING_TRANSLATION) {
                DEFAULT_INTL_CONFIG.onError(error);
            }
        },
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
