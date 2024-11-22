import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_muted_users_settings() {
    const out = html`<div id="muted-user-settings" class="settings-section" data-name="muted-users">
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Muted users"})}</h3>
            <input
                id="muted_users_search"
                class="search filter_text_input"
                type="text"
                placeholder="${$t({defaultMessage: "Filter muted users"})}"
                aria-label="${$t({defaultMessage: "Filter muted users"})}"
            />
        </div>
        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th data-sort="alphabetic" data-sort-prop="user_name">
                        ${$t({defaultMessage: "User"})}
                    </th>
                    <th data-sort="numeric" data-sort-prop="date_muted">
                        ${$t({defaultMessage: "Date muted"})}
                    </th>
                    <th class="actions">${$t({defaultMessage: "Actions"})}</th>
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
