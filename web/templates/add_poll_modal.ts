import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";
import render_poll_modal_option from "./poll_modal_option.ts";

export default function render_add_poll_modal() {
    const out = html`<form id="add-poll-form">
        <label class="poll-label">${$t({defaultMessage: "Question"})}</label>
        <div class="poll-question-input-container">
            <input
                type="text"
                id="poll-question-input"
                class="modal_text_input"
                placeholder="${$t({defaultMessage: "Your question"})}"
            />
        </div>
        <label class="poll-label">${$t({defaultMessage: "Options"})}</label>
        <p>${$t({defaultMessage: "Anyone can add more options after the poll is posted."})}</p>
        <ul class="poll-options-list" data-simplebar data-simplebar-tab-index="-1">
            ${{__html: render_poll_modal_option()}} ${{__html: render_poll_modal_option()}}
            ${{__html: render_poll_modal_option()}}
        </ul>
    </form> `;
    return to_html(out);
}
