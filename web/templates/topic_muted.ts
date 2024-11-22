import {html, to_html} from "../shared/src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_topic_muted() {
    const out = $html_t(
        {defaultMessage: "You have muted <z-stream-topic></z-stream-topic>."},
        {
            ["z-stream-topic"]: () =>
                html`<strong
                    ><span class="stream"></span> &gt; <span class="topic"></span
                ></strong>`,
        },
    );
    return to_html(out);
}
