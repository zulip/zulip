import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";

export default function render_reply_recipient_label(context) {
    const out = to_bool(context.is_dm_with_self)
        ? $html_t({defaultMessage: "Write yourself a note"})
        : $html_t(
              {defaultMessage: "Message <z-recipient-label></z-recipient-label>"},
              {
                  ["z-recipient-label"]: () =>
                      to_bool(context.has_empty_string_topic)
                          ? html`#${context.channel_name} &gt;
                                <span class="empty-topic-display"
                                    >${context.empty_string_topic_display_name}</span
                                >`
                          : context.label_text,
              },
          );
    return to_html(out);
}
