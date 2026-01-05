import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_dropdown_widget_wrapper from "./dropdown_widget_wrapper.ts";
import render_recipient_row from "./recipient_row.ts";
import render_single_message from "./single_message.ts";

export default function render_report_message_modal(context) {
    const out = html`<form id="message_report_form">
        <p>
            ${$t({
                defaultMessage:
                    "Your report will be sent to the private moderation requests channel for this organization.",
            })}
        </p>
        <div id="report-message-preview-container" class="input-group">
            ${{__html: render_recipient_row(context.recipient_row_data)}}
            ${{__html: render_single_message(context.message_container_data)}}
        </div>
        <div class="input-group">
            <label class="report-type-wrapper modal-field-label">
                ${$t({defaultMessage: "What's the problem with this message?"})}
            </label>
            ${{__html: render_dropdown_widget_wrapper({widget_name: "report_type_options"})}}
        </div>
        <div class="input-group">
            <label for="message-report-description" class="modal-field-label">
                ${$t({defaultMessage: "Can you provide more details?"})}
            </label>
            <textarea
                id="message-report-description"
                class="modal-textarea"
                rows="4"
                maxlength="1000"
            ></textarea>
        </div>
    </form> `;
    return to_html(out);
}
