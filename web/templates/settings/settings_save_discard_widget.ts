import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";

export default function render_settings_save_discard_widget(context) {
    const out = !to_bool(context.show_only_indicator)
        ? html`<div class="save-button-controls hide">
              <div class="inline-block subsection-changes-save">
                  ${{
                      __html: render_action_button({
                          label: $t({defaultMessage: "Save changes"}),
                          intent: "brand",
                          attention: "primary",
                          custom_classes: "save-button",
                      }),
                  }}
              </div>
              <div class="inline-block subsection-changes-discard">
                  ${{
                      __html: render_action_button({
                          label: $t({defaultMessage: "Discard"}),
                          intent: "neutral",
                          attention: "quiet",
                          custom_classes: "discard-button",
                      }),
                  }}
              </div>
              <div class="inline-block subsection-failed-status"><p class="hide"></p></div>
          </div> `
        : html`<div class="alert-notification ${context.section_name}-status"></div> `;
    return to_html(out);
}
