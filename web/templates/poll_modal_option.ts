import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_icon_button from "./components/icon_button.ts";

export default function render_poll_modal_option() {
    const out = html`<li class="option-row">
        <i class="zulip-icon zulip-icon-grip-vertical drag-icon"></i>
        <input
            type="text"
            class="poll-option-input modal_text_input"
            placeholder="${$t({defaultMessage: "New option"})}"
        />
        ${{
            __html: render_icon_button({
                icon: "trash",
                custom_classes: "delete-option",
                intent: "danger",
            }),
        }}
    </li> `;
    return to_html(out);
}
