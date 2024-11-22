import {html, to_html} from "../../shared/src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_compose_banner from "./compose_banner.ts";

export default function render_stream_wildcard_warning(context) {
    const out = {
        __html: render_compose_banner(
            context,
            (context1) => html`
                <p class="banner_message">
                    ${$html_t(
                        {
                            defaultMessage:
                                "Are you sure you want to send @-mention notifications to the <strong>{subscriber_count}</strong> users subscribed to #{channel_name}? If not, please edit your message to remove the <strong>@{wildcard_mention}</strong> mention.",
                        },
                        {
                            subscriber_count: context1.subscriber_count,
                            channel_name: context1.channel_name,
                            wildcard_mention: context1.wildcard_mention,
                        },
                    )}
                </p>
            `,
        ),
    };
    return to_html(out);
}
