import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
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
                <th data-sort="name">${$t({defaultMessage: "Name"})}</th>
                <th class="settings-email-column" data-sort="email">
                    ${$t({defaultMessage: "Email"})}
                </th>
                <th
                    class="user-remove-actions"
                    ${!to_bool(context.can_edit) ? html`style="display:none"` : ""}
                >
                    ${$t({defaultMessage: "Actions"})}
                </th>
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
