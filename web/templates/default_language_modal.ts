import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_default_language_modal(context) {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "A language is marked as 100% translated only if every string in the web, desktop, and mobile apps is translated, including administrative UI and error messages.",
            })}
        </p>
        <p>
            ${$html_t(
                {
                    defaultMessage:
                        "Zulip's translations are contributed by our amazing community of volunteer translators. If you'd like to help, see the <z-link>Zulip translation guidelines</z-link>.",
                },
                {
                    ["z-link"]: (content) =>
                        html`<a
                            target="_blank"
                            rel="noopener noreferrer"
                            href="https://zulip.readthedocs.io/en/latest/translating/translating.html"
                            >${content}</a
                        >`,
                },
            )}
        </p>
        <div class="default_language_modal_table">
            ${to_array(context.language_list).map(
                (language) => html`
                    <div class="language_block">
                        <a
                            class="language"
                            data-code="${language.code}"
                            data-name="${language.name}"
                        >
                            ${to_bool(language.selected)
                                ? html` <b>${language.name_with_percent}</b> `
                                : html` ${language.name_with_percent} `}
                        </a>
                    </div>
                `,
            )}
        </div> `;
    return to_html(out);
}
