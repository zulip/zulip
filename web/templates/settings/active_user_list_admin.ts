import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_filter_text_input from "./filter_text_input.ts";

export default function render_active_user_list_admin(context) {
    const out = html`<div
        id="admin-active-users-list"
        class="user-settings-section user-or-bot-settings-section"
        data-user-settings-section="active"
    >
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Users"})}</h3>
            <div class="alert-notification" id="user-field-status"></div>
            <div class="user_filters">
                ${{
                    __html: render_dropdown_widget({
                        widget_name: context.active_user_list_dropdown_widget_name,
                    }),
                }}
                ${{
                    __html: render_filter_text_input({
                        aria_label: $t({defaultMessage: "Filter users"}),
                        placeholder: $t({defaultMessage: "Filter"}),
                    }),
                }}
            </div>
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <tr>
                        <th class="active" data-sort="alphabetic" data-sort-prop="full_name">
                            ${$t({defaultMessage: "Name"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="settings-email-column" data-sort="email">
                            ${$t({defaultMessage: "Email"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="user_role" data-sort="role">
                            ${$t({defaultMessage: "Role"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="last_active" data-sort="last_active">
                            ${$t({defaultMessage: "Last active"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        ${to_bool(context.is_admin)
                            ? html` <th class="actions">${$t({defaultMessage: "Actions"})}</th> `
                            : ""}
                    </tr>
                </thead>
                <tbody
                    id="admin_users_table"
                    class="admin_user_table"
                    data-empty="${$t({defaultMessage: "No users match your filters."})}"
                ></tbody>
            </table>
        </div>
        <div id="admin_page_users_loading_indicator"></div>
    </div> `;
    return to_html(out);
}
