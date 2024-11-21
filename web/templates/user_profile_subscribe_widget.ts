import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_action_button from "./components/action_button.ts";
import render_dropdown_widget from "./dropdown_widget.ts";

export default function render_user_profile_subscribe_widget() {
    const out = html`<div class="user_profile_subscribe_widget">
        ${{__html: render_dropdown_widget({widget_name: "user_profile_subscribe"})}}
        ${{
            __html: render_action_button({
                ["aria-label"]: $t({defaultMessage: "Subscribe"}),
                intent: "brand",
                attention: "quiet",
                custom_classes: "add-subscription-button",
                label: $t({defaultMessage: "Subscribe"}),
            }),
        }}
    </div> `;
    return to_html(out);
}
