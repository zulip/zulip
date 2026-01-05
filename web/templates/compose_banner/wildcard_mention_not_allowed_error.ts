import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_wildcard_mention_not_allowed_error(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${to_bool(context1.wildcard_mention_string)
                        ? $html_t(
                              {
                                  defaultMessage:
                                      "You do not have permission to use <z-highlight>@{wildcard_mention_string}</z-highlight> mentions in this channel.",
                              },
                              {
                                  wildcard_mention_string: context1.wildcard_mention_string,
                                  ["z-highlight"]: (content) =>
                                      html`<b class="highlighted-element">${content}</b>`,
                              },
                          )
                        : $html_t(
                              {
                                  defaultMessage:
                                      "You do not have permission to use <z-highlight>@topic</z-highlight> mentions in this topic.",
                              },
                              {
                                  ["z-highlight"]: (content) =>
                                      html`<b class="highlighted-element">${content}</b>`,
                              },
                          )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
