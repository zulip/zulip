import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_allow_private_data_export_banner(context) {
    const out = {
        __html: render_modal_banner(
            context,
            () => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "Do you want to <z-link>allow your private data to be exported</z-link>?",
                        },
                        {
                            ["z-link"]: (content) =>
                                html`<a href="#settings/account-and-privacy">${content}</a>`,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
