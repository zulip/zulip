import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_stream_creation_confirmation_banner(context) {
    const out = {
        __html: render_modal_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {defaultMessage: "Channel <z-link>#{stream_name}</z-link> created!"},
                        {
                            stream_name: context1.stream_name,
                            ["z-link"]: (content) =>
                                html`<a class="stream_narrow_link" href="${context1.stream_url}"
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
