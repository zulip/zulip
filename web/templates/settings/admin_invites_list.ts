import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_display_only_pill from "../user_display_only_pill.ts";

export default function render_admin_invites_list(context) {
    const out = ((invite) =>
        html`<tr class="invite_row">
            <td>
                ${to_bool(invite.is_multiuse)
                    ? html`
                          <span class="email">
                              <a
                                  href="${invite.link_url}"
                                  target="_blank"
                                  rel="noopener noreferrer"
                              >
                                  ${$t({defaultMessage: "Invite link"})}
                              </a>
                          </span>
                      `
                    : html` <span class="email">${invite.email}</span> `}
            </td>
            ${to_bool(invite.is_admin)
                ? html`
                      <td>
                          <span class="referred_by panel_user_list">
                              ${{
                                  __html: render_user_display_only_pill({
                                      is_active: true,
                                      user_id: invite.invited_by_user_id,
                                      display_value: invite.referrer_name,
                                  }),
                              }}
                          </span>
                      </td>
                  `
                : ""}
            <td>
                <span class="invited_at">${invite.invited_absolute_time}</span>
            </td>
            <td>
                ${to_bool(invite.expiry_date_absolute_time)
                    ? html` <span class="expires_at">${invite.expiry_date_absolute_time}</span> `
                    : html`
                          <span class="expires_at">${$t({defaultMessage: "Never expires"})}</span>
                      `}
            </td>
            <td>
                <span>${invite.invited_as_text}</span>
            </td>
            <td class="actions">
                ${!to_bool(invite.is_multiuse)
                    ? html`
                          <button
                              class="button rounded small resend button-warning"
                              ${to_bool(invite.disable_buttons) ? html`disabled="disabled"` : ""}
                              data-invite-id="${invite.id}"
                          >
                              ${$t({defaultMessage: "Resend"})}
                          </button>
                      `
                    : ""}
                <button
                    class="button rounded small revoke button-danger"
                    ${to_bool(invite.disable_buttons) ? html`disabled="disabled"` : ""}
                    data-invite-id="${invite.id}"
                    data-is-multiuse="${invite.is_multiuse}"
                >
                    ${$t({defaultMessage: "Revoke"})}
                </button>
            </td>
        </tr> `)(context.invite);
    return to_html(out);
}
