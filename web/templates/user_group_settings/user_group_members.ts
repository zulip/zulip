import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_add_members_form from "./add_members_form.ts";
import render_user_group_members_table from "./user_group_members_table.ts";
import render_user_group_membership_status from "./user_group_membership_status.ts";

export default function render_user_group_members(context) {
    const out = html`<div class="member_list_settings_container">
        <div class="membership-status">
            ${{__html: render_user_group_membership_status(context)}}
        </div>
        <h4 class="user_group_setting_subsection_title">${$t({defaultMessage: "Add members"})}</h4>
        <div class="user_group_subscription_request_result banner-wrapper"></div>
        <div class="member_list_settings">
            <div class="member_list_add float-left">
                ${{__html: render_add_members_form(context)}}
            </div>
            <div class="clear-float"></div>
        </div>
        <div>
            <h4 class="inline-block user_group_setting_subsection_title">
                ${$t({defaultMessage: "Members"})}
            </h4>
            <span class="member-search float-right">
                <input
                    type="text"
                    class="search filter_text_input"
                    placeholder="${$t({defaultMessage: "Filter"})}"
                />
            </span>
        </div>
        <div class="add-group-member-loading-spinner"></div>
        <div class="member-list-box">${{__html: render_user_group_members_table(context)}}</div>
    </div> `;
    return to_html(out);
}
