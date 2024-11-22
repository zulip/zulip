import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";

export default function render_custom_user_profile_field(context) {
    const out = html`<div
        class="custom_user_field"
        name="${context.field.name}"
        data-field-id="${context.field.id}"
    >
        <span
            class="custom-user-field-label-wrapper ${to_bool(context.field.required)
                ? "required-field-wrapper"
                : ""}"
        >
            <label
                class="settings-field-label inline-block"
                for="id_custom_profile_field_input_${context.field.id}"
                >${context.field.name}</label
            >
            <span
                class="required-symbol ${!to_bool(context.is_empty_required_field) ? "hidden" : ""}"
            >
                *</span
            >
        </span>
        <div class="alert-notification custom-field-status"></div>
        <div class="settings-profile-user-field-hint">${context.field.hint}</div>
        <div
            class="settings-profile-user-field ${to_bool(context.is_empty_required_field)
                ? "empty-required-field"
                : ""} ${!to_bool(context.editable_by_user)
                ? "not-editable-by-user-input-wrapper"
                : ""}"
        >
            ${to_bool(context.is_long_text_field)
                ? html`
                      <textarea
                          id="id_custom_profile_field_input_${context.field.id}"
                          maxlength="500"
                          class="custom_user_field_value settings_textarea"
                          name="${context.field.id}"
                          ${!to_bool(context.editable_by_user) ? "disabled" : ""}
                      >
${context.field_value.value}</textarea
                      >
                  `
                : to_bool(context.is_select_field)
                  ? html`
                        <select
                            id="id_custom_profile_field_input_${context.field.id}"
                            class="custom_user_field_value ${to_bool(context.for_manage_user_modal)
                                ? "modal_select"
                                : "settings_select"} bootstrap-focus-style"
                            name="${context.field.id}"
                            ${!to_bool(context.editable_by_user) ? "disabled" : ""}
                        >
                            <option value=""></option>
                            ${to_array(context.field_choices).map(
                                (choice) => html`
                                    <option
                                        value="${choice.value}"
                                        ${to_bool(choice.selected) ? "selected" : ""}
                                    >
                                        ${choice.text}
                                    </option>
                                `,
                            )}
                        </select>
                    `
                  : to_bool(context.is_user_field)
                    ? html`
                          <div
                              class="pill-container person_picker ${!to_bool(
                                  context.editable_by_user,
                              )
                                  ? "not-editable-by-user disabled"
                                  : ""}"
                              name="${context.field.id}"
                          >
                              <div
                                  class="input"
                                  ${to_bool(context.editable_by_user)
                                      ? html`contenteditable="true"`
                                      : ""}
                              ></div>
                          </div>
                      `
                    : to_bool(context.is_date_field)
                      ? html`
                            <input
                                class="custom_user_field_value datepicker ${to_bool(
                                    context.for_manage_user_modal,
                                )
                                    ? "modal_text_input"
                                    : "settings_text_input"}"
                                name="${context.field.id}"
                                data-field-id="${context.field.id}"
                                type="text"
                                value="${context.field_value.value}"
                                ${!to_bool(context.editable_by_user) ? "disabled" : ""}
                            />
                            ${to_bool(context.editable_by_user)
                                ? html`<span class="remove_date"><i class="fa fa-close"></i></span>`
                                : ""}
                        `
                      : to_bool(context.is_url_field)
                        ? html`
                              <input
                                  id="id_custom_profile_field_input_${context.field.id}"
                                  class="custom_user_field_value ${to_bool(
                                      context.for_manage_user_modal,
                                  )
                                      ? "modal_url_input"
                                      : "settings_url_input"}"
                                  name="${context.field.id}"
                                  type="${context.field_type}"
                                  value="${context.field_value.value}"
                                  maxlength="2048"
                                  ${!to_bool(context.editable_by_user) ? "disabled" : ""}
                              />
                          `
                        : to_bool(context.is_pronouns_field)
                          ? html`
                                <input
                                    id="id_custom_profile_field_input_${context.field.id}"
                                    class="custom_user_field_value pronouns_type_field ${to_bool(
                                        context.for_manage_user_modal,
                                    )
                                        ? "modal_text_input"
                                        : "settings_text_input"}"
                                    name="${context.field.id}"
                                    type="${context.field_type}"
                                    value="${context.field_value.value}"
                                    maxlength="50"
                                    ${!to_bool(context.editable_by_user) ? "disabled" : ""}
                                />
                            `
                          : html`
                                <input
                                    id="id_custom_profile_field_input_${context.field.id}"
                                    class="custom_user_field_value ${to_bool(
                                        context.for_manage_user_modal,
                                    )
                                        ? "modal_text_input"
                                        : "settings_text_input"}"
                                    name="${context.field.id}"
                                    type="${context.field_type}"
                                    value="${context.field_value.value}"
                                    maxlength="50"
                                    ${!to_bool(context.editable_by_user) ? "disabled" : ""}
                                />
                            `}
        </div>
    </div> `;
    return to_html(out);
}
