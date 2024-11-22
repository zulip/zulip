import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_change_user_group_info_modal(context) {
    const out = html`<div>
            <label for="change_user_group_name" class="modal-field-label">
                ${$t({defaultMessage: "User group name"})}
            </label>
            <input
                type="text"
                id="change_user_group_name"
                class="modal_text_input"
                name="user_group_name"
                value="${context.group_name}"
                maxlength="${context.max_user_group_name_length}"
            />
        </div>
        <div>
            <label for="change_user_group_description" class="modal-field-label">
                ${$t({defaultMessage: "User group description"})}
            </label>
            <textarea
                id="change_user_group_description"
                class="settings_textarea"
                name="user_group_description"
            >
${context.group_description}</textarea
            >
        </div> `;
    return to_html(out);
}
