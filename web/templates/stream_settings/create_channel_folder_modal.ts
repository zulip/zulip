import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_create_channel_folder_modal(context) {
    const out = html`<div>
            <label for="new_channel_folder_name" class="modal-field-label">
                ${$t({defaultMessage: "Channel folder name"})}
            </label>
            <input
                type="text"
                id="new_channel_folder_name"
                class="modal_text_input"
                name="channel_folder_name"
                maxlength="${context.max_channel_folder_name_length}"
            />
        </div>
        <div>
            <label for="new_channel_folder_description" class="modal-field-label">
                ${$t({defaultMessage: "Description"})}
            </label>
            <textarea
                id="new_channel_folder_description"
                class="modal-textarea"
                name="channel_folder_description"
                maxlength="${context.max_channel_folder_description_length}"
            ></textarea>
        </div> `;
    return to_html(out);
}
