import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_banner from "../components/banner.ts";

export default function render_stream_settings_tip(context) {
    const out = !to_bool(context.can_change_stream_permissions_requiring_metadata_access)
        ? html` ${{
              __html: render_banner({
                  process: false,
                  close_button: false,
                  custom_classes: "admin-permissions-banner",
                  intent: "info",
                  label: $t({
                      defaultMessage: "Only channel administrators can edit these settings.",
                  }),
              }),
          }}`
        : "";
    return to_html(out);
}
