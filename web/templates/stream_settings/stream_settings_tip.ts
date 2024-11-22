import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_stream_settings_tip(context) {
    const out = !to_bool(context.can_change_stream_permissions)
        ? to_bool(context.can_change_name_description)
            ? html`
                  <div class="tip">
                      ${$t({
                          defaultMessage:
                              "Only subscribers to this channel can edit channel permissions.",
                      })}
                  </div>
              `
            : html`
                  <div class="tip">
                      ${$t({
                          defaultMessage:
                              "Only organization administrators can edit these settings.",
                      })}
                  </div>
              `
        : "";
    return to_html(out);
}
