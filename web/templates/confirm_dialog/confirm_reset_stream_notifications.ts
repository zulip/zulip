import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_inline_decorated_channel_name from "../inline_decorated_channel_name.ts";

export default function render_confirm_reset_stream_notifications(context) {
    const out = html`<p>
        ${$html_t(
            {
                defaultMessage:
                    "Are you sure you want to reset notifications for <z-stream></z-stream>?",
            },
            {
                ["z-stream"]: () => ({
                    __html: render_inline_decorated_channel_name({
                        show_colored_icon: false,
                        stream: context.sub,
                    }),
                }),
            },
        )}
    </p> `;
    return to_html(out);
}
