import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$html_t} from "../../src/i18n.ts";
import render_notification_settings from "./notification_settings.ts";
import render_preferences from "./preferences.ts";

export default function render_organization_user_settings_defaults(context) {
    const out = html`<div
        id="realm-user-default-settings"
        class="settings-section"
        data-name="organization-level-user-defaults"
    >
        ${to_bool(context.is_admin)
            ? html`
                  <div>
                      ${$html_t(
                          {
                              defaultMessage:
                                  "Configure the <z-link>default personal preference settings</z-link> for new users joining your organization.",
                          },
                          {
                              ["z-link"]: (content) =>
                                  html`<a
                                      href="/help/configure-default-new-user-settings"
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      >${content}</a
                                  >`,
                          },
                      )}
                  </div>
              `
            : ""}
        ${{
            __html: render_preferences({
                full_name: context.full_name,
                for_realm_settings: true,
                prefix: "realm_",
                ...context,
            }),
        }}
        ${{
            __html: render_notification_settings({
                for_realm_settings: true,
                prefix: "realm_",
                ...context,
            }),
        }}
    </div> `;
    return to_html(out);
}
