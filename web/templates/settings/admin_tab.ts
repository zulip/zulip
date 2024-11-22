import {html, to_html} from "../../shared/src/html.ts";
import render_admin_settings_modals from "./admin_settings_modals.ts";
import render_auth_methods_settings_admin from "./auth_methods_settings_admin.ts";
import render_bot_list_admin from "./bot_list_admin.ts";
import render_data_exports_admin from "./data_exports_admin.ts";
import render_default_streams_list_admin from "./default_streams_list_admin.ts";
import render_emoji_settings_admin from "./emoji_settings_admin.ts";
import render_linkifier_settings_admin from "./linkifier_settings_admin.ts";
import render_organization_permissions_admin from "./organization_permissions_admin.ts";
import render_organization_profile_admin from "./organization_profile_admin.ts";
import render_organization_settings_admin from "./organization_settings_admin.ts";
import render_organization_user_settings_defaults from "./organization_user_settings_defaults.ts";
import render_playground_settings_admin from "./playground_settings_admin.ts";
import render_profile_field_settings_admin from "./profile_field_settings_admin.ts";
import render_user_list_admin from "./user_list_admin.ts";

export default function render_admin_tab(context) {
    const out = html`<div class="alert" id="organization-status"></div>
        <div id="revoke_invite_modal_holder"></div>

        ${{__html: render_admin_settings_modals()}}
        ${{__html: render_organization_profile_admin(context)}}
        ${{__html: render_organization_settings_admin(context)}}
        ${{__html: render_organization_permissions_admin(context)}}
        ${{__html: render_organization_user_settings_defaults(context)}}
        ${{__html: render_emoji_settings_admin(context)}}
        ${{__html: render_user_list_admin(context)}} ${{__html: render_bot_list_admin(context)}}
        ${{__html: render_default_streams_list_admin(context)}}
        ${{__html: render_auth_methods_settings_admin(context)}}
        ${{__html: render_linkifier_settings_admin(context)}}
        ${{__html: render_playground_settings_admin(context)}}
        ${{__html: render_profile_field_settings_admin(context)}}
        ${{__html: render_data_exports_admin(context)}}`;
    return to_html(out);
}
