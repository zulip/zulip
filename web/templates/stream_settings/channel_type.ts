import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";
import render_settings_checkbox from "../settings/settings_checkbox.ts";

export default function render_channel_type(context) {
    const out = html`${{
            __html: render_dropdown_widget_with_label({
                label: $t({defaultMessage: "Who can access this channel"}),
                widget_name: context.channel_privacy_widget_name,
            }),
        }}
        <div class="history-public-to-subscribers">
            ${{
                __html: render_settings_checkbox({
                    help_link: "/help/channel-permissions#private-channels",
                    label: $t({
                        defaultMessage: "Subscribers can view messages sent before they joined",
                    }),
                    is_checked: context.history_public_to_subscribers,
                    setting_name: "history_public_to_subscribers",
                    prefix: context.prefix,
                }),
            }}
        </div> `;
    return to_html(out);
}
