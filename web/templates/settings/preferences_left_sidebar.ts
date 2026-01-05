import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";

export default function render_preferences_left_sidebar(context) {
    const out = html`<div
        class="left-sidebar-settings ${to_bool(context.for_realm_settings)
            ? "settings-subsection-parent"
            : "subsection-parent"}"
    >
        <div class="subsection-header">
            <h3 class="light">${$t({defaultMessage: "Left sidebar"})}</h3>
            ${{
                __html: render_settings_save_discard_widget({
                    show_only_indicator: !to_bool(context.for_realm_settings),
                    section_name: "left-sidebar-settings",
                }),
            }}
        </div>

        <div class="input-group">
            <label
                for="${context.prefix}web_stream_unreads_count_display_policy"
                class="settings-field-label"
                >${$t({defaultMessage: "Show unread counts for"})}</label
            >
            <select
                name="web_stream_unreads_count_display_policy"
                class="setting_web_stream_unreads_count_display_policy prop-element bootstrap-focus-style settings_select"
                id="${context.prefix}web_stream_unreads_count_display_policy"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.web_stream_unreads_count_display_policy_values,
                    }),
                }}
            </select>
        </div>

        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                render_only: context.settings_render_only.web_left_sidebar_unreads_count_summary,
                label: context.settings_label.web_left_sidebar_unreads_count_summary,
                is_checked: context.settings_object.web_left_sidebar_unreads_count_summary,
                setting_name: "web_left_sidebar_unreads_count_summary",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                render_only: context.settings_render_only.starred_message_counts,
                label: context.settings_label.starred_message_counts,
                is_checked: context.settings_object.starred_message_counts,
                setting_name: "starred_message_counts",
            }),
        }}
        ${{
            __html: render_settings_checkbox({
                prefix: context.prefix,
                help_link: "/help/channel-folders",
                render_only: context.settings_render_only.web_left_sidebar_show_channel_folders,
                label: context.settings_label.web_left_sidebar_show_channel_folders,
                is_checked: context.settings_object.web_left_sidebar_show_channel_folders,
                setting_name: "web_left_sidebar_show_channel_folders",
            }),
        }}
        <div class="input-group">
            <label for="${context.prefix}demote_inactive_streams" class="settings-field-label"
                >${$t({defaultMessage: "Hide inactive channels"})}
                ${{__html: render_help_link_widget({link: "/help/manage-inactive-channels"})}}
            </label>
            <select
                name="demote_inactive_streams"
                class="setting_demote_inactive_streams prop-element settings_select bootstrap-focus-style"
                id="${context.prefix}demote_inactive_streams"
                data-setting-widget-type="number"
            >
                ${{
                    __html: render_dropdown_options_widget({
                        option_values: context.demote_inactive_streams_values,
                    }),
                }}
            </select>
        </div>
    </div> `;
    return to_html(out);
}
