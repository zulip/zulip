import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_change_stream_info_modal(context) {
    const out = html`<div>
            <label for="change_stream_name" class="modal-field-label">
                ${$t({defaultMessage: "Channel name"})}
            </label>
            <input
                type="text"
                id="change_stream_name"
                class="modal_text_input"
                name="stream_name"
                value="${context.stream_name}"
                maxlength="${context.max_stream_name_length}"
            />
        </div>
        <div>
            <label for="change_stream_description" class="modal-field-label">
                ${$t({defaultMessage: "Description"})}
                ${{__html: render_help_link_widget({link: "/help/change-the-channel-description"})}}
            </label>
            <textarea
                id="change_stream_description"
                class="settings_textarea"
                name="stream_description"
                maxlength="${context.max_stream_description_length}"
            >
${context.stream_description}</textarea
            >
        </div> `;
    return to_html(out);
}
