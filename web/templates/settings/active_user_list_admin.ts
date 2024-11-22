import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";

export default function render_active_user_list_admin(context) {
    const out = html`<div
        id="admin-active-users-list"
        class="user-settings-section"
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
                <input
                    type="text"
                    class="search filter_text_input"
                    placeholder="${$t({defaultMessage: "Filter users"})}"
                    aria-label="${$t({defaultMessage: "Filter users"})}"
                />
            </div>
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th class="active" data-sort="alphabetic" data-sort-prop="full_name">
                        ${$t({defaultMessage: "Name"})}
                    </th>
                    <th class="settings-email-column" data-sort="email">
                        ${$t({defaultMessage: "Email"})}
                    </th>
                    <th class="user_role" data-sort="role">${$t({defaultMessage: "Role"})}</th>
                    <th class="last_active" data-sort="last_active">
                        ${$t({defaultMessage: "Last active"})}
                    </th>
                    ${to_bool(context.is_admin)
                        ? html` <th class="actions">${$t({defaultMessage: "Actions"})}</th> `
                        : ""}
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
