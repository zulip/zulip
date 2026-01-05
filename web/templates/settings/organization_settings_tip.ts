import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_banner from "../components/banner.ts";

export default function render_organization_settings_tip(context) {
    const out = !to_bool(context.is_admin)
        ? html`<div class="banner-wrapper">
              ${{
                  __html: render_banner({
                      custom_classes: "admin-permissions-banner",
                      intent: "info",
                      label: $t({
                          defaultMessage:
                              "Only organization administrators can edit these settings.",
                      }),
                  }),
              }}
          </div> `
        : "";
    return to_html(out);
}
