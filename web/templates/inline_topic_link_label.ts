import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_inline_topic_link_label(context) {
    const out = to_bool(context.is_empty_string_topic)
        ? html`<span class="stream-topic"
              >#${context.channel_name} &gt;
              <em class="empty-topic-display">${$t({defaultMessage: "general chat"})}</em></span
          >`
        : html`<span class="stream-topic"
              >#${context.channel_name} &gt; ${context.topic_display_name}</span
          >`;
    return to_html(out);
}
