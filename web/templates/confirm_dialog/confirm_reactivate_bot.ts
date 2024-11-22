import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_confirm_reactivate_bot(context) {
    const out = html`<p>
            ${$html_t(
                {
                    defaultMessage:
                        "<z-user></z-user> will have the same properties as it did prior to deactivation, including role, owner and channel subscriptions.",
                },
                {["z-user"]: () => html`<strong>${context.username}</strong>`},
            )}
        </p>
        ${to_bool(context.original_owner_deactivated)
            ? html`
                  <p>
                      ${$html_t(
                          {
                              defaultMessage:
                                  "Because the original owner of this bot <z-bot-owner></z-bot-owner> is deactivated, you will become the owner for this bot.",
                          },
                          {["z-bot-owner"]: () => html`<strong>${context.owner_name}</strong>`},
                      )}
                      ${$t({
                          defaultMessage:
                              "However, it will no longer be subscribed to the private channels that you are not subscribed to.",
                      })}
                  </p>
              `
            : ""}`;
    return to_html(out);
}
