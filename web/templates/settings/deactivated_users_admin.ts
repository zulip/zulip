import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_filter_text_input from "./filter_text_input.ts";

export default function render_deactivated_users_admin(context) {
    const out = html`<div
        id="admin-deactivated-users-list"
        class="user-settings-section user-or-bot-settings-section"
        data-user-settings-section="deactivated"
    >
        <div class="clear-float"></div>

        <div class="settings_panel_list_header">
            <h3>
                ${$t({defaultMessage: "Deactivated users"})}
                ${{
                    __html: render_help_link_widget({
                        link: "/help/deactivate-or-reactivate-a-user",
                    }),
                }}
            </h3>
            <div class="alert-notification" id="deactivated-user-field-status"></div>
            <div class="user_filters">
                ${{
                    __html: render_dropdown_widget({
                        widget_name: context.deactivated_user_list_dropdown_widget_name,
                    }),
                }}
                ${{
                    __html: render_filter_text_input({
                        aria_label: $t({defaultMessage: "Filter deactivated users"}),
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
                        <th
                            class="settings-email-column"
                            ${to_bool(context.allow_sorting_deactivated_users_list_by_email)
                                ? html`data-sort="email"`
                                : ""}
                        >
                            ${$t({defaultMessage: "Email"})}
                            ${to_bool(context.allow_sorting_deactivated_users_list_by_email)
                                ? html`
                                      <i
                                          class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                      ></i>
                                  `
                                : ""}
                        </th>
                        <th class="user_role" data-sort="role">
                            ${$t({defaultMessage: "Role"})}
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
                    id="admin_deactivated_users_table"
                    class="admin_user_table"
                    data-empty="${$t({defaultMessage: "There are no deactivated users."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No deactivated users match your filters.",
                    })}"
                ></tbody>
            </table>
        </div>
        <div id="admin_page_deactivated_users_loading_indicator"></div>
    </div> `;
    return to_html(out);
}
