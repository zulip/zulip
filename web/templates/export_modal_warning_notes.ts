import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$html_t} from "../src/i18n.ts";
import render_user_display_only_pill from "./user_display_only_pill.ts";

export default function render_export_modal_warning_notes(context) {
    const out = to_bool(context.unusable_user_count)
        ? html` <p>
                  ${$html_t(
                      {
                          defaultMessage:
                              "You don't have permission to <z-help-link>access</z-help-link> the email {unusable_user_count, plural, one {address} other {addresses}} of {unusable_user_count, plural, one {# user} other {# users}}.",
                      },
                      {
                          unusable_user_count: context.unusable_user_count,
                          ["z-help-link"]: (content) => html`
                              <a
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  href="#/help/configure-email-visibility"
                              >
                                  ${content}
                              </a>
                          `,
                      },
                  )}
                  ${$html_t({
                      defaultMessage:
                          "Accounts for users whose emails you can't access will be created with placeholder email addresses. A placeholder email must be updated by an administrator for the user to be able to log in.",
                  })}
              </p>

              ${to_bool(context.unusable_admin_user_count)
                  ? html`
                        <p>
                            ${$html_t(
                                {
                                    defaultMessage:
                                        "The following {unusable_admin_user_count, plural, one {administrator} other {administrators}} will be unable to log in: <z-user-pills></z-user-pills>",
                                },
                                {
                                    unusable_admin_user_count: context.unusable_admin_user_count,
                                    ["z-user-pills"]: () =>
                                        to_array(context.unusable_admin_users).map(
                                            (user, user_index, user_array) => html`
                                                ${{
                                                    __html: render_user_display_only_pill({
                                                        is_active: true,
                                                        img_src: user.avatar_url,
                                                        display_value: user.full_name,
                                                        user_id: user.user_id,
                                                    }),
                                                }}
                                                ${user_index !== user_array.length - 1 ? ", " : ""}
                                            `,
                                        ),
                                },
                            )}
                        </p>
                    `
                  : ""}`
        : "";
    return to_html(out);
}
