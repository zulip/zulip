import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_deactivate_realm(context) {
    const out = to_bool(context.can_set_data_deletion)
        ? html`<form id="realm-data-deletion-form">
                  <div class="input-group">
                      <label for="delete-realm-data-in" class="modal-field-label"
                          >${$t({
                              defaultMessage:
                                  "After how much time should all data for this organization be permanently deleted (users, channels, messages, etc.)?",
                          })}</label
                      >
                      <select
                          id="delete-realm-data-in"
                          name="delete-realm-data-in"
                          class="modal_select bootstrap-focus-style"
                      >
                          ${to_array(context.delete_in_options).map(
                              (option) => html`
                                  <option
                                      ${to_bool(option.default) ? "selected" : ""}
                                      value="${option.value}"
                                  >
                                      ${option.description}
                                  </option>
                              `,
                          )}
                      </select>
                      <p class="time-input-formatted-description"></p>
                      <div
                          id="custom-realm-deletion-time"
                          class="dependent-settings-block custom-time-input-container"
                      >
                          <label class="modal-field-label"
                              >${context.custom_deletion_input_label}</label
                          >
                          <input
                              id="custom-deletion-time-input"
                              name="custom-deletion-time-input"
                              class="custom-time-input-value inline-block modal_text_input"
                              type="text"
                              autocomplete="off"
                              value=""
                              maxlength="4"
                          />
                          <select
                              id="custom-deletion-time-unit"
                              name="custom-deletion-time-unit"
                              class="custom-time-input-unit bootstrap-focus-style modal_select"
                          >
                              ${to_array(context.time_choices).map(
                                  (time_unit) => html`
                                      <option value="${time_unit.name}">
                                          ${time_unit.description}
                                      </option>
                                  `,
                              )}
                          </select>
                          <p class="custom-time-input-formatted-description"></p>
                      </div>
                  </div>
              </form>
              <p>
                  ${$t({
                      defaultMessage:
                          "Are you sure you want to deactivate this organization? All users will lose access to their Zulip accounts.",
                  })}
              </p> `
        : html`<p>
              ${$t({
                  defaultMessage:
                      "Are you sure you want to deactivate this organization? All data will be immediately deleted.",
              })}
          </p> `;
    return to_html(out);
}
