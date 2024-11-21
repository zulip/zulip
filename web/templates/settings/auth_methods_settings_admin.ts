import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_banner from "../components/banner.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_auth_methods_settings_admin(context) {
    const out = html`<div
        id="organization-auth-settings"
        class="settings-section"
        data-name="auth-methods"
    >
        ${!to_bool(context.is_owner)
            ? html`
                  <div class="banner-wrapper">
                      ${{
                          __html: render_banner({
                              custom_classes: "admin-permissions-banner",
                              intent: "info",
                              label: $t({
                                  defaultMessage:
                                      "Only organization owners can edit these settings.",
                              }),
                          }),
                      }}
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
