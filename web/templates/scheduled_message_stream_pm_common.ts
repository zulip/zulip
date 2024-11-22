import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_scheduled_message_stream_pm_common(context) {
    const out = html`${to_bool(context.failed)
            ? html`<div class="error-icon-message-recipient">
                  <i
                      class="zulip-icon zulip-icon-exclamation-circle"
                      data-tippy-content="${$t({
                          defaultMessage: "This message could not be sent at the scheduled time.",
                      })}"
                  ></i>
              </div> `
            : ""}
        <div class="recipient_row_date">${context.formatted_send_at_time}</div> `;
    return to_html(out);
}
