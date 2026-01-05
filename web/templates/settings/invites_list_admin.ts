import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_banner from "../components/banner.ts";
import render_filter_text_input from "./filter_text_input.ts";

export default function render_invites_list_admin(context) {
    const out = html`<div
        id="admin-invites-list"
        class="user-settings-section"
        data-user-settings-section="invitations"
    >
        <div class="invite-user-settings-banner banner-wrapper">
            ${{
                __html: render_banner({
                    custom_classes: "admin-permissions-banner",
                    intent: "info",
                    label: $t({
                        defaultMessage:
                            "You do not have permission to send invite emails in this organization.",
                    }),
                }),
            }}
        </div>
        ${!to_bool(context.is_admin)
            ? html`
                  <div class="banner-wrapper">
                      ${{
                          __html: render_banner({
                              custom_classes: "admin-permissions-banner",
                              intent: "info",
                              label: $t({
                                  defaultMessage:
                                      "You can only view or manage invitations that you sent.",
                              }),
                          }),
                      }}
                  </div>
              `
            : ""}
        ${{
            __html: render_action_button({
                custom_classes: "user-settings-invite-user-label invite-user-link",
                intent: "brand",
                attention: "quiet",
                label: $t({defaultMessage: "Invite users to organization"}),
            }),
        }}
        <div class="settings_panel_list_header">
            <h3>${$t({defaultMessage: "Invitations"})}</h3>
            <div class="alert-notification" id="invites-field-status"></div>
            ${{
                __html: render_filter_text_input({
                    aria_label: $t({defaultMessage: "Filter invitations"}),
                    placeholder: $t({defaultMessage: "Filter"}),
                }),
            }}
        </div>

        <div class="progressive-table-wrapper" data-simplebar data-simplebar-tab-index="-1">
            <table class="table table-striped">
                <thead class="table-sticky-headers">
                    <tr>
                        <th class="active" data-sort="invitee">
                            ${$t({defaultMessage: "Invitee"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        ${to_bool(context.is_admin)
                            ? html`
                                  <th data-sort="alphabetic" data-sort-prop="referrer_name">
                                      ${$t({defaultMessage: "Invited by"})}
                                      <i
                                          class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                                      ></i>
                                  </th>
                              `
                            : ""}
                        <th data-sort="numeric" data-sort-prop="invited">
                            ${$t({defaultMessage: "Invited at"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th data-sort="numeric" data-sort-prop="expiry_date">
                            ${$t({defaultMessage: "Expires at"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th data-sort="numeric" data-sort-prop="invited_as">
                            ${$t({defaultMessage: "Invited as"})}
                            <i
                                class="table-sortable-arrow zulip-icon zulip-icon-sort-arrow-down"
                            ></i>
                        </th>
                        <th class="actions">${$t({defaultMessage: "Actions"})}</th>
                    </tr>
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
