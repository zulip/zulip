import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_skipped_marking_unread(context) {
    const out = $html_t(
        {
            defaultMessage:
                "Because you are not subscribed to <z-streams></z-streams>, messages in this channel were not marked as unread.",
        },
        {["z-streams"]: () => html`<strong>${{__html: context.streams_html}}</strong>`},
    );
    return to_html(out);
}
