import {html, to_html} from "../shared/src/html.ts";
import {to_array, to_bool} from "../src/hbs_compat.ts";
import {$html_t, $t} from "../src/i18n.ts";

export default function render_invitation_failed_error(context) {
    const out = html`<p id="invitation_error_message">${context.error_message}</p>
        ${to_bool(context.daily_limit_reached)
            ? $html_t(
                  {
                      defaultMessage:
                          "Please <z-link-support>contact support</z-link-support> for an exception or <z-link-invite-help>add users with a reusable invite link</z-link-invite-help>.",
                  },
                  {
                      ["z-link-support"]: (content) =>
                          html`<a href="https://zulip.com/help/contact-support">${content}</a>`,
                      ["z-link-invite-help"]: (content) =>
                          html`<a
                              href="https://zulip.com/help/invite-new-users#create-a-reusable-invitation-link"
                              >${content}</a
                          >`,
                  },
              )
            : ""}
        <ul>
            ${to_array(context.error_list).map((error) => html` <li>${error}</li> `)}
        </ul>
        ${to_bool(context.is_invitee_deactivated)
            ? to_bool(context.is_admin)
                ? html`
                      <p id="invitation_admin_message">
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "You can reactivate deactivated users from <z-link>organization settings</z-link>.",
                              },
                              {
                                  ["z-link"]: (content) =>
                                      html`<a href="#organization/deactivated">${content}</a>`,
                              },
                          )}
                      </p>
                  `
                : html`
                      <p id="invitation_non_admin_message">
                          ${$t({
                              defaultMessage:
                                  "Organization administrators can reactivate deactivated users.",
                          })}
                      </p>
                  `
            : ""}${to_bool(context.license_limit_reached)
            ? to_bool(context.has_billing_access)
                ? $html_t(
                      {
                          defaultMessage:
                              "To invite users, please <z-link-billing>increase the number of licenses</z-link-billing> or <z-link-help-page>deactivate inactive users</z-link-help-page>.",
                      },
                      {
                          ["z-link-billing"]: (content) => html`<a href="/billing/">${content}</a>`,
                          ["z-link-help-page"]: (content) =>
                              html`<a
                                  href="/help/deactivate-or-reactivate-a-user"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  >${content}</a
                              >`,
                      },
                  )
                : $html_t(
                      {
                          defaultMessage:
                              "Please ask a billing administrator to <z-link-billing>increase the number of licenses</z-link-billing> or <z-link-help-page>deactivate inactive users</z-link-help-page>, and try again.",
                      },
                      {
                          ["z-link-billing"]: (content) => html`<a href="/billing/">${content}</a>`,
                          ["z-link-help-page"]: (content) =>
                              html`<a
                                  href="/help/deactivate-or-reactivate-a-user"
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  >${content}</a
                              >`,
                      },
                  )
            : ""}`;
    return to_html(out);
}
