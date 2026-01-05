import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_stream_does_not_exist_error(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "The channel <z-highlight>#{channel_name}</z-highlight> does not exist. Manage your subscriptions <z-link>on your Channels page</z-link>.",
                        },
                        {
                            channel_name: context1.channel_name,
                            ["z-highlight"]: (content) =>
                                html`<b class="highlighted-element">${content}</b>`,
                            ["z-link"]: (content) => html`<a href="#channels/all">${content}</a>`,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
