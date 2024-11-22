import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_stream_info_banner(context) {
    const out = {
        __html: render_modal_banner(
            context,
            () => html`
                <p class="banner_message">
                    ${$html_t({
                        defaultMessage:
                            "Channels organize conversations based on who needs to see them.",
                    })}
                </p>
            `,
        ),
    };
    return to_html(out);
}
