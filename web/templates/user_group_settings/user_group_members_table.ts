import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_user_group_members_table(context) {
    const out = html`<div
        class="member_list_container"
        data-simplebar
        data-simplebar-tab-index="-1"
    >
        <div class="member_list_loading_indicator"></div>
        <table class="member-list table table-striped">
            <thead class="table-sticky-headers">
                <tr>
                    <th class="panel_user_list" data-sort="name">
                        ${$t({defaultMessage: "Name"})}
                        <i class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"></i>
                    </th>
                    <th class="settings-email-column" data-sort="email">
                        ${$t({defaultMessage: "Email"})}
                        <i class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"></i>
                    </th>
                    <th
                        class="remove-button-column"
                        ${!to_bool(context.can_remove_members) ? html`style="display:none"` : ""}
                    ></th>
                </tr>
            </thead>
            <tbody
                class="member_table"
                data-empty="${$t({defaultMessage: "This group has no members."})}"
                data-search-results-empty="${$t({
                    defaultMessage: "No group members match your current filter.",
                })}"
            ></tbody>
        </table>
    </div> `;
    return to_html(out);
}
