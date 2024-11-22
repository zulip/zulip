import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";

export default function render_invites_list_admin(context) {
    const out = html`<div
        id="admin-invites-list"
        class="user-settings-section"
        data-user-settings-section="invitations"
    >
        <div class="tip invite-user-settings-tip"></div>
        ${!to_bool(context.is_admin)
            ? html`
                  <div class="tip">
                      ${$t({
                          defaultMessage: "You can only view or manage invitations that you sent.",
                      })}
                  </div>
              `
            : ""}
        <a class="invite-user-link" role="button"
            ><i class="fa fa-user-plus" aria-hidden="true"></i>${$t({
                defaultMessage: "Invite users to organization",
            })}</a
        >

        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Invitations"})}</h3>
            <div class="alert-notification" id="invites-field-status"></div>
            <input
                type="text"
                class="search filter_text_input"
                placeholder="${$t({defaultMessage: "Filter invitations"})}"
                aria-label="${$t({defaultMessage: "Filter invitations"})}"
            />
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped">
                <thead class="table-sticky-headers">
                    <th class="active" data-sort="invitee">${$t({defaultMessage: "Invitee"})}</th>
                    ${to_bool(context.is_admin)
                        ? html`
                              <th data-sort="alphabetic" data-sort-prop="referrer_name">
                                  ${$t({defaultMessage: "Invited by"})}
                              </th>
                          `
                        : ""}
                    <th data-sort="numeric" data-sort-prop="invited">
                        ${$t({defaultMessage: "Invited at"})}
                    </th>
                    <th data-sort="numeric" data-sort-prop="expiry_date">
                        ${$t({defaultMessage: "Expires at"})}
                    </th>
                    <th data-sort="numeric" data-sort-prop="invited_as">
                        ${$t({defaultMessage: "Invited as"})}
                    </th>
                    <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                </thead>
                <tbody
                    id="admin_invites_table"
                    class="admin_invites_table"
                    data-empty="${$t({defaultMessage: "There are no invitations."})}"
                    data-search-results-empty="${$t({
                        defaultMessage: "No invitations match your current filter.",
                    })}"
                ></tbody>
            </table>
        </div>
        <div id="admin_page_invites_loading_indicator"></div>
    </div> `;
    return to_html(out);
}
