import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import render_inline_decorated_channel_name from "./inline_decorated_channel_name.ts";

export default function render_inline_stream_or_topic_reference(context) {
    const out = html`<span class="stream-or-topic-reference"
        >${to_bool(context.stream)
            ? html` ${{
                  __html: render_inline_decorated_channel_name({
                      show_colored_icon: context.show_colored_icon,
                      stream: context.stream,
                  }),
              }}
              ${to_bool(context.topic_display_name) ? html`&gt; ` : ""}`
            : ""}<span
            ${to_bool(context.is_empty_string_topic) ? html`class="empty-topic-display"` : ""}
            >${context.topic_display_name}</span
        >
    </span> `;
    return to_html(out);
}
