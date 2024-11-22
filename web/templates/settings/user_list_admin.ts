import {html, to_html} from "../../shared/src/html.ts";
import render_active_user_list_admin from "./active_user_list_admin.ts";
import render_deactivated_users_admin from "./deactivated_users_admin.ts";
import render_invites_list_admin from "./invites_list_admin.ts";

export default function render_user_list_admin(context) {
    const out = html`<div id="admin-user-list" class="settings-section" data-name="users">
        <div class="tab-container"></div>

        ${{__html: render_active_user_list_admin(context)}}
        ${{__html: render_deactivated_users_admin(context)}}
        ${{__html: render_invites_list_admin(context)}}
    </div> `;
    return to_html(out);
}
