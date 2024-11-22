import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_stream(context) {
    const out = html`<p>
    ${$html_t({defaultMessage: "Archiving this channel will:"})}
</p>
<p>
    <ul>
        <li>${$html_t({defaultMessage: "Remove it from the left sidebar for all users."})}</li>
        <li>${$html_t({defaultMessage: "Prevent new messages from being sent to this channel."})}</li>
        <li>${$html_t({defaultMessage: "Prevent messages in this channel from being edited, deleted, or moved."})}</li>
    </ul>
${$html_t({defaultMessage: "Users can still search for messages in archived channels.<br/> This action cannot be undone."})}</p>
${
    to_bool(context.is_announcement_stream)
        ? html`<p class="notification_stream_archive_warning">
                  ${$html_t({
                      defaultMessage:
                          "Archiving this channel will also disable settings that were configured to use this channel:",
                  })}
              </p>
              <ul>
                  ${to_bool(context.is_new_stream_announcements_stream)
                      ? html` <li>${$html_t({defaultMessage: "New channel notifications"})}</li> `
                      : ""}${to_bool(context.is_signup_announcements_stream)
                      ? html` <li>${$html_t({defaultMessage: "New user notifications"})}</li> `
                      : ""}${to_bool(context.is_zulip_update_announcements_stream)
                      ? html` <li>${$html_t({defaultMessage: "Zulip update announcements"})}</li> `
                      : ""}
              </ul> `
        : ""
}`;
    return to_html(out);
}
