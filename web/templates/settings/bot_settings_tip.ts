import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_banner from "../components/banner.ts";

export default function render_bot_settings_tip(context) {
    const out = !to_bool(context.can_create_any_bots)
        ? to_bool(context.can_create_incoming_webhooks)
            ? html` ${{
                  __html: render_banner({
                      custom_classes: "admin-permissions-banner",
                      intent: "info",
                      label: $t({
                          defaultMessage: "You can create bots that can only send messages.",
                      }),
                  }),
              }}`
            : html` ${{
                  __html: render_banner({
                      custom_classes: "admin-permissions-banner",
                      intent: "info",
                      label: $t({defaultMessage: "You do not have permission to create bots."}),
                  }),
              }}`
        : "";
    return to_html(out);
}
