import {html, to_html} from "../../shared/src/html.ts";
import render_preferences_emoji from "./preferences_emoji.ts";
import render_preferences_general from "./preferences_general.ts";
import render_preferences_information from "./preferences_information.ts";
import render_preferences_navigation from "./preferences_navigation.ts";

export default function render_preferences(context) {
    const out = html`<form class="preferences-settings-form">
        ${{__html: render_preferences_general(context)}}
        ${{__html: render_preferences_emoji(context)}}
        ${{__html: render_preferences_navigation(context)}}
        ${{__html: render_preferences_information(context)}}
    </form> `;
    return to_html(out);
}
