import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";

export default function render_edit_embedded_bot_service(context) {
    const out = to_bool(context.service)
        ? to_bool(context.service.config_data)
            ? html`
                  <div id="config_edit_inputbox">
                      ${Object.entries(context.service.config_data).map(
                          ([entry_key, entry]) => html`
                              <div class="input-group">
                                  <label
                                      for="embedded_bot_${entry_key}_edit"
                                      class="modal-field-label"
                                      >${entry_key}</label
                                  >
                                  <input
                                      type="text"
                                      name="${entry_key}"
                                      id="embedded_bot_${entry_key}_edit"
                                      class="modal_text_input"
                                      maxlength="1000"
                                      value="${entry}"
                                  />
                              </div>
                          `,
                      )}
                  </div>
              `
            : ""
        : "";
    return to_html(out);
}
