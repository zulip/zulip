import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";

export default function render_edit_embedded_bot_service(context) {
    const out = to_bool(context.service)
        ? to_bool(context.service.config_data)
            ? html`
                  <div id="config_edit_inputbox">
                      ${Object.entries(context.service.config_data).map(
                          ([context1_key, context1]) => html`
                              <div class="input-group">
                                  <label
                                      for="embedded_bot_${context1_key}_edit"
                                      class="modal-field-label"
                                      >${context1_key}</label
                                  >
                                  <input
                                      type="text"
                                      name="${context1_key}"
                                      id="embedded_bot_${context1_key}_edit"
                                      class="modal_text_input"
                                      maxlength="1000"
                                      value="${context1}"
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
