import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_unknown_zoom_user_error(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "Your Zulip account email (<z-highlight>{email}</z-highlight>) is not linked to this organization's Zoom account.",
                        },
                        {
                            email: context1.email,
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
