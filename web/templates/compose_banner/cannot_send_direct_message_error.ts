import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_cannot_send_direct_message_error(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${context1.error_message}
                    ${$html_t(
                        {defaultMessage: "<z-link>Learn more.</z-link>"},
                        {
                            ["z-link"]: (content) =>
                                html`<a
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    href="/help/restrict-direct-messages"
                                    >${content}</a
                                >`,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
