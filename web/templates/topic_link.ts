import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";

export default function render_topic_link(context) {
    const out = to_bool(context.is_empty_string_topic)
        ? html`<a class="stream-topic" data-stream-id="${context.channel_id}" href="${context.href}"
              >#${context.channel_name} &gt;
              <span class="empty-topic-display">${context.topic_display_name}</span></a
          >`
        : html`<a class="stream-topic" data-stream-id="${context.channel_id}" href="${context.href}"
              >#${context.channel_name} &gt; ${context.topic_display_name}</a
          >`;
    return to_html(out);
}
