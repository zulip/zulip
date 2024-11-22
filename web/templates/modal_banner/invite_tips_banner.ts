import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";
import render_modal_banner from "./modal_banner.ts";

export default function render_invite_tips_banner(context) {
    const out = html`${!to_bool(context.realm_has_description)
        ? {
              __html: render_modal_banner(
                  context,
                  () => html`
                      <p class="banner_message">
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "You may want to <z-link>configure</z-link> your organization's login page prior to inviting users.",
                              },
                              {
                                  ["z-link"]: (content) =>
                                      html`<a href="#organization/organization-profile"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </p>
                  `,
              ),
          }
        : !to_bool(context.realm_has_user_set_icon)
          ? {
                __html: render_modal_banner(
                    context,
                    () => html`
                        <p class="banner_message">
                            ${$html_t(
                                {
                                    defaultMessage:
                                        "You may want to <z-link>upload a profile picture</z-link> for your organization prior to inviting users.",
                                },
                                {
                                    ["z-link"]: (content) =>
                                        html`<a href="#organization/organization-profile"
                                            >${content}</a
                                        >`,
                                },
                            )}
                        </p>
                    `,
                ),
            }
          : ""}${!to_bool(context.realm_has_custom_profile_fields)
        ? {
              __html: render_modal_banner(
                  context,
                  () => html`
                      <p class="banner_message">
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "You may want to configure <z-link-1>default new user settings</z-link-1> and <z-link-2>custom profile fields</z-link-2> prior to inviting users.",
                              },
                              {
                                  ["z-link-1"]: (content) =>
                                      html`<a href="#organization/organization-level-user-defaults"
                                          >${content}</a
                                      >`,
                                  ["z-link-2"]: (content) =>
                                      html`<a href="#organization/profile-field-settings"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </p>
                  `,
              ),
          }
        : ""}`;
    return to_html(out);
}
