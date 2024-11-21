import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_stream(context) {
    const out = html`<p>${$html_t({defaultMessage: "Archiving this channel will:"})}</p>
        <ul>
            <li>${$html_t({defaultMessage: "Remove it from the left sidebar for all users."})}</li>
            <li>
                ${$html_t({
                    defaultMessage: "Prevent new messages from being sent to this channel.",
                })}
            </li>
            <li>
                ${$html_t({
                    defaultMessage:
                        "Prevent messages in this channel from being edited, deleted, or moved.",
                })}
            </li>
            ${to_bool(context.is_announcement_stream)
                ? html`
                      <li>
                          ${$html_t({
                              defaultMessage:
                                  "Disable announcements that are currently sent to this channel:",
                          })}
                          <ul>
                              ${to_bool(context.is_moderation_request_channel)
                                  ? html`
                                        <li>${$html_t({defaultMessage: "Moderation requests"})}</li>
                                    `
                                  : ""}${to_bool(context.is_new_stream_announcements_stream)
                                  ? html`
                                        <li>
                                            ${$html_t({
                                                defaultMessage: "New channel announcements",
                                            })}
                                        </li>
                                    `
                                  : ""}${to_bool(context.is_signup_announcements_stream)
                                  ? html`
                                        <li>
                                            ${$html_t({defaultMessage: "New user announcements"})}
                                        </li>
                                    `
                                  : ""}${to_bool(context.is_zulip_update_announcements_stream)
                                  ? html`
                                        <li>
                                            ${$html_t({
                                                defaultMessage: "Zulip update announcements",
                                            })}
                                        </li>
                                    `
                                  : ""}
                          </ul>
                      </li>
                  `
                : ""}
        </ul>
        <p>
            ${$html_t({
                defaultMessage:
                    "Users can still search for messages in archived channels. You can always unarchive this channel.",
            })}
        </p> `;
    return to_html(out);
}
