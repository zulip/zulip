import {html, to_html} from "../../shared/src/html.ts";
import render_preferences from "./preferences.ts";

export default function render_user_preferences(context) {
    const out = html`<div id="user-preferences" class="settings-section" data-name="preferences">
        ${{__html: render_preferences({for_realm_settings: false, prefix: "user_", ...context})}}
    </div> `;
    return to_html(out);
}
