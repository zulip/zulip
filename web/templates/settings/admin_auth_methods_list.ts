import {html, to_html} from "../../shared/src/html.ts";
import render_settings_checkbox from "./settings_checkbox.ts";

export default function render_admin_auth_methods_list(context) {
    const out = html`<div class="method_row" data-method="${context.method}">
        ${{
            __html: render_settings_checkbox({
                skip_prop_element: true,
                tooltip_text: context.unavailable_reason,
                is_disabled: context.disable_configure_auth_method,
                label: context.method,
                is_checked: context.enabled,
                prefix: context.prefix,
                setting_name: "realm_authentication_methods",
            }),
        }}
    </div> `;
    return to_html(out);
}
