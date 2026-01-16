import Handlebars from "handlebars/runtime.js";
import assert from "minimalistic-assert";
import {z} from "zod/mini";

import * as common from "./common.ts";
import {default_html_elements, intl} from "./i18n.ts";
import {postprocess_content} from "./postprocess_content.ts";
import {user_settings} from "./user_settings.ts";

// Below, we register Zulip-specific extensions to the Handlebars API.
//
// IMPORTANT: When adding a new Handlebars helper, update the
// knownHelpers array in the webpack config so that webpack knows your
// helper is registered at runtime and don't try to require them when
// bundling.

// We don't want to wait for DOM ready to register the Handlebars helpers
// below. There's no need to, as they do not access the DOM.
// Furthermore, waiting for DOM ready would introduce race conditions with
// other DOM-ready callbacks that attempt to render templates.

Handlebars.registerHelper({
    eq(a, b) {
        return a === b;
    },
    and(...args: unknown[]) {
        args.pop(); // Handlebars options
        if (args.length === 0) {
            return true;
        }
        const last = args.pop();
        for (const arg of args) {
            if (!arg || Handlebars.Utils.isEmpty(arg)) {
                return arg;
            }
        }
        return last;
    },
    or(...args: unknown[]) {
        args.pop(); // Handlebars options
        if (args.length === 0) {
            return false;
        }
        const last = args.pop();
        for (const arg of args) {
            if (arg && !Handlebars.Utils.isEmpty(arg)) {
                return arg;
            }
        }
        return last;
    },
    not(a) {
        return !a || Handlebars.Utils.isEmpty(a);
    },
});

type Context = Record<string, unknown>;

Handlebars.registerHelper("t", function (this: Context, message: string) {
    // Marks a string for translation.
    // Example usage 1:
    //     {{t "some English text"}}
    //
    // Example usage 2:
    //     {{t "This {variable} will get value from the current context"}}
    //
    // Note: use `{` and `}` instead of `{{` and `}}` to declare
    // variables.

    message = message
        .trim()
        .split("\n")
        .map((s) => s.trim())
        .join(" ");
    const descriptor = {id: message, defaultMessage: message};
    return intl.formatMessage(
        descriptor,
        Object.fromEntries(
            Object.entries(this).flatMap(([key, value]) =>
                typeof value === "string" || typeof value === "number" || value instanceof Date
                    ? [[key, value]]
                    : [],
            ),
        ),
    );
});

Handlebars.registerHelper("tr", function (this: Context, options: Handlebars.HelperOptions) {
    // Marks a block for translation.
    // Example usage 1:
    //     {{#tr}}
    //         <p>some English text</p>
    //     {{/tr}}
    //
    // Example usage 2:
    //     {{#tr}}
    //         <p>This {variable} will get value from the current context</p>
    //     {{/tr}}
    //
    // Note: use `{` and `}` instead of `{{` and `}}` to declare
    // variables.
    const message = options
        .fn(this)
        .trim()
        .split("\n")
        .map((s) => s.trim())
        .join(" ");
    const descriptor = {id: message, defaultMessage: message};
    const partials: Partial<Record<string, (context: Context, options: unknown) => string>> =
        "partials" in options.fn &&
        typeof options.fn.partials === "object" &&
        options.fn.partials !== null
            ? options.fn.partials
            : {};
    const result = intl.formatMessage(descriptor, {
        ...default_html_elements,
        ...Object.fromEntries(
            Object.entries(partials).map(([name, value]) => [
                name,
                (content_html: string[]) =>
                    value!(this, {data: {"partial-block": () => content_html.join("")}}),
            ]),
        ),
        ...Object.fromEntries(
            Object.entries(this).flatMap(([key, value]): [string, string | number | Date][] =>
                typeof value === "string"
                    ? [[key, Handlebars.Utils.escapeExpression(value)]]
                    : typeof value === "number" || value instanceof Date
                      ? [[key, value]]
                      : [],
            ),
        ),
    });
    return new Handlebars.SafeString(result);
});

Handlebars.registerHelper(
    "rendered_markdown",
    (content: string) => new Handlebars.SafeString(postprocess_content(content)),
);

Handlebars.registerHelper("numberFormat", (number: number) => number.toLocaleString());

Handlebars.registerHelper("tooltip_hotkey_hints", (...args) => {
    args.pop(); // Handlebars options
    const hotkeys: string[] = args;
    let hotkey_hints = "";
    common.adjust_mac_hotkey_hints(hotkeys);
    for (const hotkey of hotkeys) {
        hotkey_hints += `<span class="tooltip-hotkey-hint">${hotkey}</span>`;
    }
    const result = `<span class="tooltip-hotkey-hints">${hotkey_hints}</span>`;
    return new Handlebars.SafeString(result);
});

Handlebars.registerHelper("popover_hotkey_hints", (...args) => {
    args.pop(); // Handlebars options
    const hotkeys: string[] = args;
    let hotkey_hints = "";
    common.adjust_mac_hotkey_hints(hotkeys);
    const shift_hotkey_exists = common.adjust_shift_hotkey(hotkeys);
    for (const hotkey of hotkeys) {
        // The ⌘ symbol isn't vertically centered, so we use an icon.
        if (hotkey === "⌘") {
            hotkey_hints += `<span class="popover-menu-hotkey-hint"><i class="zulip-icon zulip-icon-mac-command" aria-hidden="true"></i></span>`;
        } else {
            hotkey_hints += `<span class="popover-menu-hotkey-hint">${hotkey}</span>`;
        }
    }
    if (shift_hotkey_exists) {
        return new Handlebars.SafeString(
            `<span class="popover-menu-hotkey-hints popover-contains-shift-hotkey" data-hotkey-hints="${hotkeys.join(",")}">${hotkey_hints}</span>`,
        );
    }
    return new Handlebars.SafeString(
        `<span class="popover-menu-hotkey-hints">${hotkey_hints}</span>`,
    );
});

const list_format_options_schema = z.object({
    style: z.optional(z.enum(["narrow", "long", "short"])),
    type: z.optional(z.enum(["conjunction", "disjunction", "unit"])),
});

Handlebars.registerHelper(
    "list_each",
    function (this: unknown, context: unknown, options: Handlebars.HelperOptions) {
        const {fn, inverse} = options;
        const items_html: string[] = [];
        let empty = false;
        assert("each" in Handlebars.helpers);
        const ret: unknown = Handlebars.helpers["each"].call(this, context, {
            ...options,
            fn(item_context: unknown, item_options?: Handlebars.RuntimeOptions) {
                items_html.push(fn(item_context, item_options));
                return "";
            },
            inverse(item_context: unknown, item_options?: Handlebars.RuntimeOptions) {
                empty = true;
                return inverse(item_context, item_options);
            },
        });
        if (empty) {
            return ret;
        }
        assert.equal(ret, "");
        /* istanbul ignore if */
        if (Intl.ListFormat === undefined) {
            return items_html.join(", ");
        }
        return new Intl.ListFormat(
            user_settings.default_language,
            list_format_options_schema.parse(options.hash),
        )
            .formatToParts(items_html)
            .map((part) =>
                part.type === "element"
                    ? part.value
                    : Handlebars.Utils.escapeExpression(part.value),
            )
            .join("");
    },
);
