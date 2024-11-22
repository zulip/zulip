import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_confirm_revoke_invite(context) {
    const out = to_bool(context.is_multiuse)
        ? to_bool(context.referred_by)
            ? html`<p>
                  ${$html_t(
                      {
                          defaultMessage:
                              "Are you sure you want to revoke this invitation link created by <strong>{referred_by}</strong>?",
                      },
                      {referred_by: context.referred_by},
                  )}
              </p> `
            : html`<p>
                  ${$html_t({
                      defaultMessage: "Are you sure you want to revoke this invitation link?",
                  })}
              </p> `
        : html`<p>
              ${$html_t(
                  {
                      defaultMessage:
                          "Are you sure you want to revoke the invitation to <strong>{email}</strong>?",
                  },
                  {email: context.email},
              )}
          </p> `;
    return to_html(out);
}
