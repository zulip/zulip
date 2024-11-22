import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";

export default function render_poll_modal_option() {
    const out = html`<li class="option-row">
        <i class="zulip-icon zulip-icon-grip-vertical drag-icon"></i>
        <input
            type="text"
            class="poll-option-input modal_text_input"
            placeholder="${$t({defaultMessage: "New option"})}"
        />
        <button
            type="button"
            class="button rounded small delete-option"
            title="${$t({defaultMessage: "Delete"})}"
        >
            <i class="fa fa-trash-o" aria-hidden="true"></i>
        </button>
    </li> `;
    return to_html(out);
}
