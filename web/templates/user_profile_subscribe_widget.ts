import {html, to_html} from "../shared/src/html.ts";
import {$t} from "../src/i18n.ts";
import render_dropdown_widget from "./dropdown_widget.ts";

export default function render_user_profile_subscribe_widget() {
    const out = html`<div class="user_profile_subscribe_widget">
        ${{__html: render_dropdown_widget({widget_name: "user_profile_subscribe"})}}
        <div class="add-subscription-button-wrapper">
            <button
                type="button"
                name="subscribe"
                class="add-subscription-button button small rounded"
            >
                ${$t({defaultMessage: "Subscribe"})}
            </button>
        </div>
    </div> `;
    return to_html(out);
}
