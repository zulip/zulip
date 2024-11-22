import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_wildcard_mention_not_allowed_error(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${to_bool(context1.wildcard_mention_string)
                        ? html`
                              ${$html_t(
                                  {
                                      defaultMessage:
                                          "You do not have permission to use <b>@{wildcard_mention_string}</b> mentions in this channel.",
                                  },
                                  {wildcard_mention_string: context1.wildcard_mention_string},
                              )}
                          `
                        : html`
                              ${$html_t({
                                  defaultMessage:
                                      "You do not have permission to use <b>@topic</b> mentions in this topic.",
                              })}
                          `}
                </p>
            `,
        ),
    };
    return to_html(out);
}
