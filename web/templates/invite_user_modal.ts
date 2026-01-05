import {to_array, to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_guest_visible_users_message from "./guest_visible_users_message.ts";
import render_help_link_widget from "./help_link_widget.ts";

export default function render_invite_user_modal(context) {
    const out = html`<div class="invite-user-modal-banners">
            <div id="invite-success-banner-container" class="banner-wrapper"></div>
            ${!to_bool(context.user_has_email_set)
                ? html` <div class="demo-organization-add-email-banner banner-wrapper"></div> `
                : ""}${to_bool(context.development_environment)
                ? html`
                      <div id="dev-env-email-access-banner-container" class="banner-wrapper"></div>
                  `
                : ""}
            <div class="invite-setup-tips-container banner-wrapper"></div>
        </div>
        <form id="invite-user-form">
            <div class="input-group">
                <div id="invite_users_option_tabs_container"></div>
                <div id="invitee_emails_container">
                    <label for="invitee_emails" class="modal-field-label"
                        >${$t({defaultMessage: "Emails (one on each line or comma-separated)"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/invite-new-users#send-email-invitations",
                            }),
                        }}
                    </label>
                    <div
                        class="pill-container ${!to_bool(context.user_has_email_set)
                            ? "not-editable-by-user"
                            : ""}"
                    >
                        <div
                            class="input"
                            ${to_bool(context.user_has_email_set)
                                ? html`contenteditable="true"`
                                : ""}
                        ></div>
                    </div>
                </div>
            </div>
            <div class="input-group" id="receive-invite-acceptance-notification-container">
                <label class="checkbox display-block">
                    <input type="checkbox" id="receive-invite-acceptance-notification" checked />
                    <span class="rendered-checkbox"></span>
                    ${$t({
                        defaultMessage: "Send me a direct message when my invitation is accepted",
                    })}
                </label>
            </div>
            <div class="input-group">
                <label for="expires_in" class="modal-field-label"
                    >${$t({defaultMessage: "Invitation expires after"})}</label
                >
                <select
                    id="expires_in"
                    name="expires_in"
                    class="invite-user-select modal_select bootstrap-focus-style"
                >
                    ${to_array(context.expires_in_options).map(
                        (option) => html`
                            <option
                                ${to_bool(option.default) ? "selected" : ""}
                                value="${option.value}"
                            >
                                ${option.description}
                            </option>
                        `,
                    )}
                </select>
                <p class="time-input-formatted-description"></p>
                <div
                    id="custom-invite-expiration-time"
                    class="dependent-settings-block custom-time-input-container"
                >
                    <label class="modal-field-label">${$t({defaultMessage: "Custom time"})}</label>
                    <input
                        id="custom-expiration-time-input"
                        name="custom-expiration-time-input"
                        class="custom-time-input-value inline-block"
                        type="text"
                        autocomplete="off"
                        value=""
                        maxlength="3"
                    />
                    <select
                        id="custom-expiration-time-unit"
                        name="custom-expiration-time-unit"
                        class="custom-time-input-unit invite-user-select modal_select bootstrap-focus-style"
                    >
                        ${to_array(context.time_choices).map(
                            (time_unit) => html`
                                <option value="${time_unit.name}">${time_unit.description}</option>
                            `,
                        )}
                    </select>
                    <p class="custom-time-input-formatted-description"></p>
                </div>
            </div>
            <div class="input-group">
                <label for="invite_as" class="modal-field-label"
                    >${$t({defaultMessage: "Users join as"})}
                    ${{__html: render_help_link_widget({link: "/help/user-roles"})}}
                </label>
                <select
                    id="invite_as"
                    name="invite_as"
                    class="invite-user-select modal_select bootstrap-focus-style"
                >
                    <option value="${context.invite_as_options.guest.code}">
                        ${$t({defaultMessage: "Guests"})}
                    </option>
                    <option selected="selected" value="${context.invite_as_options.member.code}">
                        ${$t({defaultMessage: "Members"})}
                    </option>
                    ${to_bool(context.is_admin)
                        ? html`
                              <option value="${context.invite_as_options.moderator.code}">
                                  ${$t({defaultMessage: "Moderators"})}
                              </option>
                              <option value="${context.invite_as_options.admin.code}">
                                  ${$t({defaultMessage: "Administrators"})}
                              </option>
                          `
                        : ""}${to_bool(context.is_owner)
                        ? html`
                              <option value="${context.invite_as_options.owner.code}">
                                  ${$t({defaultMessage: "Owners"})}
                              </option>
                          `
                        : ""}
                </select>
            </div>
            <div class="input-group">
                <label>${$t({defaultMessage: "Channels they should join"})}</label>
                <div id="streams_to_add">
                    ${to_bool(context.show_select_default_streams_option)
                        ? html`
                              <div class="select_default_streams">
                                  <label class="checkbox display-block modal-field-label">
                                      <input
                                          type="checkbox"
                                          id="invite_select_default_streams"
                                          checked="checked"
                                      />
                                      <span class="rendered-checkbox"></span>
                                      ${$t({
                                          defaultMessage: "Default channels for this organization",
                                      })}
                                  </label>
                              </div>
                          `
                        : ""}
                    <div id="invite_streams_container" class="add_streams_container">
                        <div class="pill-container stream_picker">
                            <div
                                class="input"
                                contenteditable="true"
                                data-placeholder="${$t({defaultMessage: "Add channels"})}"
                            ></div>
                        </div>
                    </div>
                </div>
            </div>
            <div id="guest_visible_users_container" class="input-group" style="display: none;">
                ${{__html: render_guest_visible_users_message()}}
            </div>
            ${to_bool(context.show_group_pill_container)
                ? html`
                      <div class="input-group">
                          <label class="modal-field-label"
                              >${$t({defaultMessage: "User groups they should join"})}
                              ${{
                                  __html: render_help_link_widget({link: "/help/user-groups"}),
                              }}</label
                          >
                          <div id="user-groups-to-add">
                              <div
                                  id="invite-user-group-container"
                                  class="add-user-group-container"
                              >
                                  <div class="pill-container">
                                      <div
                                          class="input"
                                          contenteditable="true"
                                          data-placeholder="${$t({
                                              defaultMessage: "Add user groups",
                                          })}"
                                      ></div>
                                  </div>
                              </div>
                          </div>
                      </div>
                  `
                : ""}${to_bool(context.is_admin)
                ? html`
                      <div class="input-group">
                          ${to_bool(context.default_welcome_message_custom_text.length)
                              ? html`
                                    <label class="checkbox display-block modal-field-label">
                                        <input
                                            type="checkbox"
                                            id="send_default_realm_welcome_message_custom_text"
                                            checked="checked"
                                        />
                                        <span class="rendered-checkbox"></span>
                                        ${$t({
                                            defaultMessage:
                                                "Send the default Welcome Bot message configured for this organization",
                                        })}
                                    </label>
                                `
                              : html`
                                    <label class="checkbox display-block modal-field-label">
                                        <input
                                            type="checkbox"
                                            id="send_custom_welcome_message_custom_text"
                                        />
                                        <span class="rendered-checkbox"></span>
                                        ${$t({defaultMessage: "Send a custom Welcome Bot message"})}
                                    </label>
                                `}
                          <div id="invite_welcome_message_custom_text_container">
                              <label
                                  for="invite_welcome_custom_message_text"
                                  class="modal-field-label"
                                  >${$t({defaultMessage: "Message text"})}</label
                              >
                              <textarea
                                  id="invite_welcome_custom_message_text"
                                  name="invite_welcome_message_custom_text"
                                  class="modal-textarea"
                                  maxlength="8000"
                                  rows="3"
                              >
${context.default_welcome_message_custom_text}</textarea
                              >
                          </div>
                      </div>
                  `
                : ""}
        </form> `;
    return to_html(out);
}
