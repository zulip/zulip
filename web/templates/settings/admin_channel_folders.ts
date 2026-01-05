import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";

export default function render_admin_channel_folders(context) {
    const out = html`<div
        id="channel-folder-settings"
        class="settings-section"
        data-name="channel-folders"
    >
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Channel folders"})}</h3>
            <div class="alert-notification" id="admin-channel-folder-status"></div>
            ${to_bool(context.is_admin)
                ? html` ${{
                      __html: render_action_button({
                          intent: "brand",
                          attention: "quiet",
                          label: $t({defaultMessage: "Add a new channel folder"}),
                          custom_classes: "add-channel-folder-button",
                      }),
                  }}`
                : ""}
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped admin_channel_folders_table">
                <thead>
                    <tr>
                        <th>${$t({defaultMessage: "Name"})}</th>
                        <th>${$t({defaultMessage: "Description"})}</th>
                        ${to_bool(context.is_admin)
                            ? html` <th class="actions">${$t({defaultMessage: "Actions"})}</th> `
                            : ""}
                    </tr>
                </thead>
                <tbody
                    id="admin_channel_folders_table"
                    data-empty="${$t({defaultMessage: "No channel folders configured."})}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
