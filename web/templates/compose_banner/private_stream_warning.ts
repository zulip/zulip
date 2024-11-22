import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_private_stream_warning(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "Warning: <strong>#{channel_name}</strong> is a private channel.",
                        },
                        {channel_name: context1.channel_name},
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
