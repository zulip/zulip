import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_settings_save_discard_widget(context) {
    const out = !to_bool(context.show_only_indicator)
        ? html`<div class="save-button-controls hide">
              <div class="inline-block subsection-changes-save">
                  <button
                      class="save-discard-widget-button button primary save-button"
                      data-status="save"
                  >
                      <span class="fa fa-spinner fa-spin save-discard-widget-button-loading"></span>
                      <span class="fa fa-check save-discard-widget-button-icon"></span>
                      <span class="save-discard-widget-button-text">
                          ${$t({defaultMessage: "Save changes"})}
                      </span>
                  </button>
              </div>
              <div class="inline-block subsection-changes-discard">
                  <button class="save-discard-widget-button button discard-button">
                      <span class="fa fa-times save-discard-widget-button-icon"></span>
                      <span class="save-discard-widget-button-text">
                          ${$t({defaultMessage: "Discard"})}
                      </span>
                  </button>
              </div>
              <div class="inline-block subsection-failed-status"><p class="hide"></p></div>
          </div> `
        : html`<div class="alert-notification ${context.section_name}-status"></div> `;
    return to_html(out);
}
