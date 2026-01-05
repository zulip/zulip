import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_help_link_widget from "../help_link_widget.ts";

export default function render_channel_folder(context) {
    const out = html`<div class="channel-folder-subsection">
        <div class="input-group channel-folder-container">
            ${
                /* This is a modified version of dropdown_widget_with_label.hbs
        component so that we can show dropdown button and button to create
        a new folder on same line without having to add much CSS with
        hardcoded margin and padding values. */ ""
            }
            <label class="settings-field-label" for="${context.channel_folder_widget_name}_widget">
                ${$t({defaultMessage: "Channel folder"})}
                ${{__html: render_help_link_widget({link: "/help/channel-folders"})}}
            </label>
            <span
                class="prop-element hide"
                id="id_${context.channel_folder_widget_name}"
                data-setting-widget-type="dropdown-list-widget"
                data-setting-value-type="number"
            ></span>
            <div class="dropdown_widget_with_label_wrapper channel-folder-widget-container">
                ${{
                    __html: render_dropdown_widget({
                        widget_name: context.channel_folder_widget_name,
                    }),
                }}
                ${to_bool(context.is_admin)
                    ? html` ${{
                          __html: render_action_button({
                              custom_classes: "create-channel-folder-button",
                              type: "button",
                              intent: "neutral",
                              attention: "quiet",
                              label: $t({defaultMessage: "Create new folder"}),
                          }),
                      }}`
                    : ""}
            </div>
        </div>

        <span class="settings-field-label no-folders-configured-message">
            ${$t({defaultMessage: "There are no channel folders configured in this organization."})}
            ${{__html: render_help_link_widget({link: "/help/channel-folders"})}}
        </span>
    </div> `;
    return to_html(out);
}
