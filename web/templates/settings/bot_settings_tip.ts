import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_bot_settings_tip(context) {
    const out =
        context.realm_bot_creation_policy === context.permission_type.admins_only.code
            ? html`
                  <div class="tip">
                      ${$t({
                          defaultMessage:
                              "This organization is configured so that only administrators can add bots.",
                      })}
                  </div>
              `
            : context.realm_bot_creation_policy === context.permission_type.restricted.code
              ? html`
                    <div class="tip">
                        ${$t({
                            defaultMessage:
                                "This organization is configured so that only administrators can add generic bots.",
                        })}
                    </div>
                `
              : html`
                    <div class="tip">
                        ${$t({
                            defaultMessage:
                                "This organization is configured so that anyone can add bots.",
                        })}
                    </div>
                `;
    return to_html(out);
}
