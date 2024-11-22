import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_stream_settings_checkbox(context) {
    const out = /* If setting is disabled on realm level, then render setting as control-label-disabled and do not set setting value. Setting status should not change on any click handler, as it is disabled at realm level. */ html`<div
        class="sub_setting_checkbox"
    >
        <div
            id="sub_${context.setting_name}_setting"
            class="${to_bool(context.disabled_realm_setting)
                ? "control-label-disabled\n      "
                : to_bool(context.notification_setting)
                  ? "sub_notification_setting"
                  : ""}"
        >
            <span
                ${to_bool(context.disabled_realm_setting) &&
                context.setting_name === "push_notifications"
                    ? html`class="tippy-zulip-tooltip"
                      data-tooltip-template-id="mobile-push-notification-tooltip-template"`
                    : ""}
            >
                <label class="checkbox">
                    <input
                        id="${context.setting_name}_${context.stream_id}"
                        name="${context.setting_name}"
                        class="sub_setting_control"
                        type="checkbox"
                        ${to_bool(context.is_checked) ? "checked" : ""}
                        ${to_bool(context.is_disabled) ? html`disabled="disabled"` : ""}
                    />
                    <span class="rendered-checkbox"></span>
                </label>
                <label class="inline" for="${context.setting_name}_${context.stream_id}">
                    ${context.label}
                </label>
            </span>
        </div>
        ${context.setting_name === "is_muted"
            ? html` ${{__html: render_help_link_widget({link: "/help/mute-a-channel"})}}`
            : context.setting_name === "push_notifications"
              ? html`
                    ${{
                        __html: render_help_link_widget({
                            link: "/help/mobile-notifications#enabling-push-notifications-for-self-hosted-servers",
                        }),
                    }}
                `
              : ""}
    </div> `;
    return to_html(out);
}
