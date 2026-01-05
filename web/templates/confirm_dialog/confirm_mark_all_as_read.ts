import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_confirm_mark_all_as_read() {
    const out = html`<p>
            ${$t({
                defaultMessage:
                    "Which messages do you want to mark as read? This action cannot be undone.",
            })}
        </p>
        <div class="input-group">
            <select id="mark_as_read_option" class="modal_select bootstrap-style-font">
                <option value="muted_topics">${$t({defaultMessage: "Muted topics"})}</option>
                <option value="topics_not_followed" selected>
                    ${$t({defaultMessage: "Topics you don't follow"})}
                </option>
                <option value="all_messages">${$t({defaultMessage: "All messages"})}</option>
            </select>
            <p id="message_count" class="message_count"></p>
        </div> `;
    return to_html(out);
}
