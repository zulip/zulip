import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";

export default function render_user_group_settings_empty_notice(context) {
    const out = html`<div class="no-groups-to-show-message">
        <span class="settings-empty-option-text">
            ${context.empty_user_group_list_message}
            ${to_bool(context.all_groups_tab)
                ? to_bool(context.can_create_user_groups)
                    ? html`
                          <a href="#groups/new">${$t({defaultMessage: "Create a user group"})}</a>
                      `
                    : ""
                : html` <a href="#groups/all">${$t({defaultMessage: "View all user groups"})}</a> `}
        </span>
    </div> `;
    return to_html(out);
}
