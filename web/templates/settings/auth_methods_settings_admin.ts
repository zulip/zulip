import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_auth_methods_settings_admin(context) {
    const out = html`<div
        id="organization-auth-settings"
        class="settings-section"
        data-name="auth-methods"
    >
        ${!to_bool(context.is_owner)
            ? html`
                  <div class="tip">
                      ${$t({defaultMessage: "Only organization owners can edit these settings."})}
                  </div>
              `
            : ""}${!to_bool(context.user_has_email_set)
            ? html`
                  <div class="tip">
                      ${$html_t(
                          {
                              defaultMessage:
                                  "You must <z-link>configure your email</z-link> to access this feature.",
                          },
                          {
                              ["z-link"]: (content) =>
                                  html`<a
                                      href="/help/demo-organizations#configure-email-for-demo-organization-owner"
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      >${content}</a
                                  >`,
                          },
                      )}
                  </div>
              `
            : ""}
        <form class="admin-realm-form org-authentications-form">
            <div id="org-auth_settings" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Authentication methods"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "auth_settings",
                        }),
                    }}
                </div>

                <div>
                    <p>
                        ${$t({
                            defaultMessage:
                                "Configure the authentication methods for your organization.",
                        })}
                    </p>
                    <div
                        id="id_realm_authentication_methods"
                        class="prop-element"
                        data-setting-widget-type="auth-methods"
                    >
                        ${
                            /* Empty div is intentional, it will get populated by a dedicated template */ ""
                        }
                    </div>
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
