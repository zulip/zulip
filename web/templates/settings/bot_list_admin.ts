import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$html_t, $t} from "../../src/i18n.ts";

export default function render_bot_list_admin(context) {
    const out = html`<div id="admin-bot-list" class="settings-section" data-name="bot-list-admin">
        <div class="bot-settings-tip" id="admin-bot-settings-tip"></div>
        <div class="clear-float"></div>
        <div>
            ${$t({defaultMessage: "You are viewing all the bots in this organization."})}
            <span
                class="add-new-bots"
                ${!to_bool(context.can_create_new_bots) ? html`style="display: none;"` : ""}
            >
                ${$html_t(
                    {
                        defaultMessage:
                            "You can <z-link-new-bot>add a new bot</z-link-new-bot> or <z-link-manage-bot>manage</z-link-manage-bot> your own bots.",
                    },
                    {
                        ["z-link-new-bot"]: (content) =>
                            html`<a class="add-a-new-bot">${content}</a>`,
                        ["z-link-manage-bot"]: (content) =>
                            html`<a href="/#settings/your-bots">${content}</a>`,
                    },
                )}
            </span>
            <span
                class="manage-your-bots"
                ${!(!to_bool(context.can_create_new_bots) && to_bool(context.has_bots))
                    ? html`style="display: none;"`
                    : ""}
            >
                ${$html_t(
                    {defaultMessage: "You can <z-link>manage</z-link> your own bots."},
                    {["z-link"]: (content) => html`<a href="/#settings/your-bots">${content}</a>`},
                )}
            </span>
        </div>
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Bots"})}</h3>
            <div class="alert-notification" id="bot-field-status"></div>
            <input
                type="text"
                class="search filter_text_input"
                placeholder="${$t({defaultMessage: "Filter bots"})}"
                aria-label="${$t({defaultMessage: "Filter bots"})}"
            />
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped wrapped-table">
                <thead class="table-sticky-headers">
                    <th class="active" data-sort="alphabetic" data-sort-prop="full_name">
                        ${$t({defaultMessage: "Name"})}
                    </th>
                    <th class="settings-email-column" data-sort="email">
                        ${$t({defaultMessage: "Email"})}
                    </th>
                    <th class="user_role" data-sort="role">${$t({defaultMessage: "Role"})}</th>
                    <th data-sort="bot_owner">${$t({defaultMessage: "Owner"})}</th>
                    <th data-sort="alphabetic" data-sort-prop="bot_type" class="bot_type">
                        ${$t({defaultMessage: "Bot type"})}
                    </th>
                    ${to_bool(context.is_admin)
                        ? html` <th class="actions">${$t({defaultMessage: "Actions"})}</th> `
                        : ""}
                </thead>
                <tbody
                    id="admin_bots_table"
                    class="admin_bot_table"
                    data-empty="${$t({defaultMessage: "There are no bots."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No bots match your current filter.",
                    })}"
                ></tbody>
            </table>
        </div>
        <div id="admin_page_bots_loading_indicator"></div>
    </div> `;
    return to_html(out);
}
