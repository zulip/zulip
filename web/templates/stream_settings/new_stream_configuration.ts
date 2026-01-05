import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_settings_checkbox from "../settings/settings_checkbox.ts";
import render_announce_stream_checkbox from "./announce_stream_checkbox.ts";
import render_channel_folder from "./channel_folder.ts";
import render_channel_permissions from "./channel_permissions.ts";
import render_channel_type from "./channel_type.ts";

export default function render_new_stream_configuration(context) {
    const out = html`${{
            __html: render_channel_type({
                channel_privacy_widget_name: "new_channel_privacy",
                ...context,
            }),
        }}
        ${to_bool(context.ask_to_announce_stream)
            ? html`
                  <div id="announce-new-stream">
                      ${{__html: render_announce_stream_checkbox(context)}}
                  </div>
              `
            : ""}
        <div class="default-stream">
            ${{
                __html: render_settings_checkbox({
                    help_link: "/help/set-default-channels-for-new-users",
                    label: $t({defaultMessage: "Default channel for new users"}),
                    is_checked: context.check_default_stream,
                    setting_name: "is_default_stream",
                    prefix: context.prefix,
                }),
            }}
        </div>

        ${{__html: render_channel_folder({is_stream_edit: false, ...context})}}
        <div class="advanced-configurations-container">
            <div class="advance-config-title-container">
                <div class="advance-config-toggle-area">
                    <i
                        class="fa fa-sm fa-caret-right toggle-advanced-configurations-icon"
                        aria-hidden="true"
                    ></i>
                    <h3 class="stream_setting_subsection_title">
                        <span>${$t({defaultMessage: "Advanced configuration"})}</span>
                    </h3>
                </div>
            </div>
            <div class="advanced-configurations-collapase-view hide">
                ${{__html: render_channel_permissions({is_stream_edit: false, ...context})}}
            </div>
        </div> `;
    return to_html(out);
}
