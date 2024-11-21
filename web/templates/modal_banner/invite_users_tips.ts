import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_invite_users_tips(context) {
    const out = html`${$t({
            defaultMessage:
                "You may want to complete the following setup steps prior to inviting users:",
        })}
        <ul class="invite-tips-list">
            ${!to_bool(context.realm_has_description)
                ? html`
                      <li>
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "<z-link>Configure</z-link> your organization's login page.",
                              },
                              {
                                  ["z-link"]: (content) =>
                                      html`<a
                                          class="banner-link"
                                          href="#organization/organization-profile"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </li>
                  `
                : !to_bool(context.realm_has_user_set_icon)
                  ? html`
                        <li>
                            ${$html_t(
                                {
                                    defaultMessage:
                                        "<z-link>Upload a profile picture</z-link> for your organization.",
                                },
                                {
                                    ["z-link"]: (content) =>
                                        html`<a
                                            class="banner-link"
                                            href="#organization/organization-profile"
                                            >${content}</a
                                        >`,
                                },
                            )}
                        </li>
                    `
                  : ""}${!to_bool(context.realm_has_custom_profile_fields)
                ? html`
                      <li>
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "Configure <z-link-1>default new user settings</z-link-1> and <z-link-2>custom profile fields</z-link-2>.",
                              },
                              {
                                  ["z-link-1"]: (content) =>
                                      html`<a
                                          class="banner-link"
                                          href="#organization/organization-level-user-defaults"
                                          >${content}</a
                                      >`,
                                  ["z-link-2"]: (content) =>
                                      html`<a
                                          class="banner-link"
                                          href="#organization/profile-field-settings"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </li>
                  `
                : ""}
        </ul> `;
    return to_html(out);
}
