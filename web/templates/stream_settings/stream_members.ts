import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_settings_checkbox from "./../settings/settings_checkbox.ts";
import render_add_subscribers_form from "./add_subscribers_form.ts";
import render_stream_members_table from "./stream_members_table.ts";

export default function render_stream_members(context) {
    const out = html`<div class="subscriber_list_settings_container no-display">
            <h4 class="stream_setting_subsection_title">
                ${$t({defaultMessage: "Add subscribers"})}
            </h4>
            <div class="subscriber_list_settings">
                <div class="subscriber_list_add float-left">
                    <div class="stream_subscription_request_result banner-wrapper"></div>
                    ${{__html: render_add_subscribers_form(context)}}
                </div>
                <div class="clear-float"></div>
            </div>
            <div>
                <div
                    class="subsection-parent send_notification_to_new_subscribers_container inline-block"
                >
                    ${{
                        __html: render_settings_checkbox({
                            label: $t({
                                defaultMessage:
                                    "Send notification message to newly subscribed users",
                            }),
                            is_checked: true,
                            setting_name: "send_notification_to_new_subscribers",
                        }),
                    }}
                </div>
            </div>
            <div>
                <h4 class="inline-block stream_setting_subsection_title">
                    ${$t({defaultMessage: "Subscribers"})}
                </h4>
                <span class="subscriber-search float-right">
                    <input
                        type="text"
                        class="search filter_text_input"
                        placeholder="${$t({defaultMessage: "Filter"})}"
                    />
                </span>
            </div>
            <div class="add-subscriber-loading-spinner"></div>
            <div class="subscriber-list-box">${{__html: render_stream_members_table(context)}}</div>
        </div>
        <div class="subscriber-list-settings-loading"></div> `;
    return to_html(out);
}
