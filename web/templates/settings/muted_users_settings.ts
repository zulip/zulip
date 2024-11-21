import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_filter_text_input from "./filter_text_input.ts";

export default function render_muted_users_settings() {
    const out = html`<div id="muted-user-settings" class="settings-section" data-name="muted-users">
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Muted users"})}</h3>
            ${{
                __html: render_filter_text_input({
                    aria_label: $t({defaultMessage: "Filter muted users"}),
                    placeholder: $t({defaultMessage: "Filter"}),
                    id: "muted_users_search",
                }),
            }}
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <tr>
                        <th data-sort="alphabetic" data-sort-prop="user_name">
                            ${$t({defaultMessage: "User"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th data-sort="numeric" data-sort-prop="date_muted">
                            ${$t({defaultMessage: "Date muted"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                    </tr>
                </thead>
                <tbody
                    id="muted_users_table"
                    data-empty="${$t({defaultMessage: "You have not muted any users yet."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No users match your current filter.",
                    })}"
                ></tbody>
            </table>
        </div>
    </div> `;
    return to_html(out);
}
