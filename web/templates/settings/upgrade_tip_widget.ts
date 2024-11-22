import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t} from "../../src/i18n.ts";

export default function render_upgrade_tip_widget(context) {
    const out = html`<div>
        ${!to_bool(context.zulip_plan_is_not_limited)
            ? to_bool(context.is_business_type_org)
                ? html`
                      <a
                          href="/upgrade/"
                          class="upgrade-tip"
                          target="_blank"
                          rel="noopener noreferrer"
                      >
                          ${context.upgrade_text_for_wide_organization_logo}
                      </a>
                  `
                : html`
                      <div class="upgrade-or-sponsorship-tip">
                          ${$html_t(
                              {
                                  defaultMessage:
                                      "Available on Zulip Cloud Standard. <z-link-upgrade>Upgrade</z-link-upgrade> or <z-link-sponsorship>request sponsorship</z-link-sponsorship> to access.",
                              },
                              {
                                  ["z-link-upgrade"]: (content) =>
                                      html`<a
                                          href="/upgrade/"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          >${content}</a
                                      >`,
                                  ["z-link-sponsorship"]: (content) =>
                                      html`<a
                                          href="/sponsorship/"
                                          target="_blank"
                                          rel="noopener noreferrer"
                                          >${content}</a
                                      >`,
                              },
                          )}
                      </div>
                  `
            : ""}
    </div> `;
    return to_html(out);
}
