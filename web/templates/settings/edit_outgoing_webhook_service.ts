import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_edit_outgoing_webhook_service(context) {
    const out = html`<div class="input-group">
            <label for="edit_service_base_url">${$t({defaultMessage: "Endpoint URL"})}</label>
            <input
                id="edit_service_base_url"
                type="text"
                name="service_payload_url"
                class="edit_service_base_url required modal_text_input"
                value="${context.service.base_url}"
                maxlength="2083"
            />
            <div>
                <label for="edit_service_base_url" generated="true" class="text-error"></label>
            </div>
        </div>
        <div class="input-group">
            <label for="edit_service_interface">${$t({defaultMessage: "Webhook format"})}</label>
            <select
                id="edit_service_interface"
                class="modal_select bootstrap-focus-style"
                name="service_interface"
            >
                <option value="1">Zulip</option>
                <option value="2">${$t({defaultMessage: "Slack-compatible"})}</option>
            </select>
        </div> `;
    return to_html(out);
}
