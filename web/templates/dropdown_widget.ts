import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";

export default function render_dropdown_widget(context) {
    const out = html`<button
        id="${context.widget_name}_widget"
        class="dropdown-widget-button"
        type="button"
        ${to_bool(context.is_setting_disabled) ? "disabled" : ""}
        ${to_bool(context.disable_keyboard_focus) ? html`tabindex="-1"` : ""}
        name="${context.widget_name}"
    >
        <span class="dropdown_widget_value"
            >${to_bool(context.default_text) ? context.default_text : ""}</span
        >
        <i class="zulip-icon zulip-icon-chevron-down"></i>
    </button> `;
    return to_html(out);
}
