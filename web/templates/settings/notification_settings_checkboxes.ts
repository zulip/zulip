import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";

export default function render_notification_settings_checkboxes(context) {
    const out = html`<td>
        <span
            ${to_bool(context.is_mobile_checkbox) && to_bool(context.is_disabled)
                ? html` class="tippy-zulip-tooltip"
                  data-tooltip-template-id="mobile-push-notification-tooltip-template"`
                : ""}
        >
            <label class="checkbox">
                <input
                    type="checkbox"
                    name="${context.setting_name}"
                    id="${context.prefix}${context.setting_name}"
                    ${to_bool(context.is_disabled) ? " disabled " : ""}
                    ${to_bool(context.is_checked) ? html`checked="checked"` : ""}
                    data-setting-widget-type="boolean"
                    class="${context.setting_name}${!to_bool(context.is_disabled)
                        ? " prop-element"
                        : ""}"
                />
                <span class="rendered-checkbox"></span>
            </label>
        </span>
    </td> `;
    return to_html(out);
}
