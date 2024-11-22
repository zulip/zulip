import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_user(context) {
    const out = html`<p>
            ${$html_t(
                {
                    defaultMessage:
                        "When you deactivate <z-user></z-user>, they will be immediately logged out.",
                },
                {
                    ["z-user"]: () =>
                        html`<strong>${context.username}</strong>${to_bool(context.email)
                                ? html` &lt;${context.email}&gt;`
                                : ""}`,
                },
            )}
        </p>
        <p>
            ${$t({
                defaultMessage:
                    "Their password will be cleared from our systems, and any bots they maintain will be disabled.",
            })}
        </p>
        <p>
            ${$html_t(
                {
                    defaultMessage:
                        "<strong>{username}</strong> has {number_of_invites_by_user} unexpired invitations.",
                },
                {
                    username: context.username,
                    number_of_invites_by_user: context.number_of_invites_by_user,
                },
            )}${to_bool(context.bots_owned_by_user)
                ? html`
                      ${$t({defaultMessage: "They administer the following bots:"})}
                      <ul>
                          ${to_array(context.bots_owned_by_user).map(
                              (bot) => html` <li>${bot.full_name}</li> `,
                          )}
                      </ul>
                  `
                : ""}
        </p>
        <label class="checkbox">
            <input type="checkbox" class="send_email" />
            <span class="rendered-checkbox"></span>
            ${$t({defaultMessage: "Notify this user by email?"})}
        </label>
        <div class="email_field">
            <p class="border-top">
                <strong>${$t({defaultMessage: "Subject"})}:</strong>
                ${$t(
                    {defaultMessage: "Notification of account deactivation on {realm_name}"},
                    {realm_name: context.realm_name},
                )}
            </p>
            <div class="email-body">
                <p>
                    ${$html_t(
                        {
                            defaultMessage:
                                "Your Zulip account on <z-link></z-link> has been deactivated, and you will no longer be able to log in.",
                        },
                        {
                            ["z-link"]: () =>
                                html`<a href="${context.realm_url}">${context.realm_url}</a>`,
                        },
                    )}
                </p>
                <p>${$t({defaultMessage: "The administrators provided the following comment:"})}</p>
                <textarea
                    class="email_field_textarea settings_textarea"
                    rows="8"
                    maxlength="2000"
                ></textarea>
            </div>
        </div> `;
    return to_html(out);
}
