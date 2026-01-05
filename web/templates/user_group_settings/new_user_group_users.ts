import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_add_members_form from "./add_members_form.ts";

export default function render_new_user_group_users() {
    const out = html`<div class="member_list_add float-left">
            ${{__html: render_add_members_form({hide_add_button: true})}}
        </div>
        <br />

        <div class="create_member_list_header">
            <h4 class="user_group_setting_subsection_title">
                ${$t({defaultMessage: "Members preview"})}
            </h4>
            <input
                class="add-user-list-filter filter_text_input"
                name="user_list_filter"
                type="text"
                autocomplete="off"
                placeholder="${$t({defaultMessage: "Filter"})}"
            />
        </div>

        <div class="add-group-member-loading-spinner"></div>

        <div class="member-list-box">
            <div class="member_list_container" data-simplebar data-simplebar-tab-index="-1">
                <table class="member-list table table-striped">
                    <thead class="table-sticky-headers">
                        <tr>
                            <th
                                class="panel_user_list"
                                data-sort="alphabetic"
                                data-sort-prop="full_name"
                            >
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
                            <th class="action-column">${$t({defaultMessage: "Action"})}</th>
                        </tr>
                    </thead>
                    <tbody
                        id="create_user_group_members"
                        class="member_table"
                        data-empty="${$t({defaultMessage: "This group has no members."})}"
                        data-search-results-empty="${$t({
                            defaultMessage: "No group members match your current filter.",
                        })}"
                    ></tbody>
                </table>
            </div>
        </div> `;
    return to_html(out);
}
