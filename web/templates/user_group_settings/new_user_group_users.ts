import {html, to_html} from "../../shared/src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_add_members_form from "./add_members_form.ts";

export default function render_new_user_group_users() {
    const out = html`<div class="member_list_add float-left">
            ${{__html: render_add_members_form({hide_add_button: true})}}
        </div>
        <br />

        ${$t({defaultMessage: "Do you want to add everyone?"})}
        <button class="add_all_users_to_user_group small button rounded sea-green">
            ${$t({defaultMessage: "Add all users"})}
        </button>

        <div class="create_member_list_header">
            <h4 class="user_group_setting_subsection_title">
                ${$t({defaultMessage: "Members preview"})}
            </h4>
            <input
                class="add-user-list-filter filter_text_input"
                name="user_list_filter"
                type="text"
                autocomplete="off"
                placeholder="${$t({defaultMessage: "Filter members"})}"
            />
        </div>

        <div class="member-list-box">
            <div class="member_list_container" data-simplebar data-simplebar-tab-index="-1">
                <table class="member-list table table-striped">
                    <thead class="table-sticky-headers">
                        <th data-sort="alphabetic" data-sort-prop="full_name">
                            ${$t({defaultMessage: "Name"})}
                        </th>
                        <th class="settings-email-column" data-sort="email">
                            ${$t({defaultMessage: "Email"})}
                        </th>
                        <th>${$t({defaultMessage: "Action"})}</th>
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
