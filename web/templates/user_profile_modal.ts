import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";
import render_user_custom_profile_fields from "./user_custom_profile_fields.ts";
import render_user_full_name from "./user_full_name.ts";
import render_user_profile_subscribe_widget from "./user_profile_subscribe_widget.ts";

export default function render_user_profile_modal(context) {
    const out = html`<div
        class="micromodal"
        id="user-profile-modal"
        data-user-id="${context.user_id}"
        aria-hidden="true"
    >
        <div class="modal__overlay" tabindex="-1">
            <div
                class="modal__container"
                role="dialog"
                aria-modal="true"
                aria-labelledby="dialog_title"
            >
                <div class="modal__header">
                    <h1 class="modal__title user-profile-name-heading" id="name">
                        ${!to_bool(context.is_bot)
                            ? to_bool(context.is_active)
                                ? html`
                                      <div
                                          class="tippy-zulip-tooltip"
                                          data-tippy-content="${context.last_seen}"
                                      >
                                          <span
                                              class="${context.user_circle_class} user_circle user_profile_presence"
                                              data-presence-indicator-user-id="${context.user_id}"
                                          ></span>
                                      </div>
                                  `
                                : html`
                                      <div>
                                          <i
                                              class="fa fa-ban deactivated-user-icon tippy-zulip-tooltip"
                                              data-tippy-content="Deactivated user"
                                          ></i>
                                      </div>
                                  `
                            : ""}${to_bool(context.is_bot)
                            ? html` <i class="zulip-icon zulip-icon-bot" aria-hidden="true"></i> `
                            : ""}
                        <span class="user-profile-name"
                            >${{__html: render_user_full_name({name: context.full_name})}}</span
                        >
                        <a
                            class="copy-link-to-user-profile user-profile-manage-own-copy-link-button"
                            tabindex="0"
                            data-user-id="${context.user_id}"
                        >
                            <i
                                class="zulip-icon zulip-icon-link tippy-zulip-tooltip "
                                data-tippy-content="${$t({defaultMessage: "Copy link to profile"})}"
                                aria-hidden="true"
                            ></i>
                        </a>
                        ${to_bool(context.is_me)
                            ? html`
                                  <a
                                      class="user-profile-manage-own-edit-button"
                                      href="/#settings/profile"
                                  >
                                      <i
                                          class="zulip-icon zulip-icon-edit tippy-zulip-tooltip"
                                          data-tippy-content="${$t({
                                              defaultMessage: "Edit profile",
                                          })}"
                                          aria-hidden="true"
                                      ></i>
                                  </a>
                              `
                            : ""}${to_bool(context.can_manage_profile)
                            ? html`
                                  <div class="user-profile-manage-others-edit-button">
                                      <i
                                          class="zulip-icon zulip-icon-edit tippy-zulip-tooltip"
                                          data-tippy-content="${$t({
                                              defaultMessage: "Manage user",
                                          })}"
                                          aria-hidden="true"
                                      ></i>
                                  </div>
                              `
                            : ""}
                    </h1>
                    <button
                        class="modal__close"
                        aria-label="${$t({defaultMessage: "Close modal"})}"
                        data-micromodal-close
                    ></button>
                </div>
                <div id="tab-toggle"></div>
                <main
                    class="modal__body"
                    id="body"
                    data-simplebar
                    data-simplebar-tab-index="-1"
                    data-simplebar-auto-hide="false"
                >
                    <div class="tab-data">
                        <div class="tabcontent active" id="profile-tab">
                            <div class="top">
                                <div class="col-wrap col-left">
                                    <div id="default-section">
                                        ${to_bool(context.email)
                                            ? html`
                                                  <div id="email" class="default-field">
                                                      <div class="name">
                                                          ${$t({defaultMessage: "Email"})}
                                                      </div>
                                                      <div class="value">${context.email}</div>
                                                  </div>
                                              `
                                            : ""}
                                        <div id="user-id" class="default-field">
                                            <div class="name">
                                                ${$t({defaultMessage: "User ID"})}
                                            </div>
                                            <div class="value">${context.user_id}</div>
                                        </div>
                                        <div id="user-type" class="default-field">
                                            <div class="name">${$t({defaultMessage: "Role"})}</div>
                                            ${to_bool(context.is_bot)
                                                ? to_bool(context.is_system_bot)
                                                    ? html`
                                                          <div class="value">
                                                              ${$t({defaultMessage: "System bot"})}
                                                          </div>
                                                      `
                                                    : html`
                                                          <div class="value">
                                                              ${$t({defaultMessage: "Bot"})}
                                                              <span class="lowercase"
                                                                  >(${context.user_type})</span
                                                              >
                                                          </div>
                                                      `
                                                : html`
                                                      <div class="value">${context.user_type}</div>
                                                  `}
                                        </div>
                                        <div id="date-joined" class="default-field">
                                            <div class="name">
                                                ${$t({defaultMessage: "Joined"})}
                                            </div>
                                            <div class="value">${context.date_joined}</div>
                                        </div>
                                        ${to_bool(context.user_time)
                                            ? html`
                                                  <div class="default-field">
                                                      <div class="name">
                                                          ${$t({defaultMessage: "Local time"})}
                                                      </div>
                                                      <div class="value">${context.user_time}</div>
                                                  </div>
                                              `
                                            : ""}
                                    </div>
                                </div>
                                <div class="col-wrap col-right">
                                    <div
                                        id="avatar"
                                        ${to_bool(context.user_is_guest)
                                            ? html` class="guest-avatar" `
                                            : ""}
                                        style="background-image: url('${context.user_avatar}');"
                                    ></div>
                                </div>
                            </div>
                            <div class="bottom">
                                <div id="content">
                                    ${to_bool(context.is_bot)
                                        ? html` <div class="field-section">
                                                  <div class="name">
                                                      ${$t({defaultMessage: "Bot type"})}
                                                  </div>
                                                  <div class="bot_info_value">
                                                      ${context.bot_type}
                                                  </div>
                                              </div>
                                              ${to_bool(context.bot_owner)
                                                  ? html`
                                                        <div
                                                            class="field-section bot_owner_user_field"
                                                            data-field-id="${context.bot_owner
                                                                .user_id}"
                                                        >
                                                            <div class="name">
                                                                ${$t({defaultMessage: "Owner"})}
                                                            </div>
                                                            <div
                                                                class="pill-container not-editable"
                                                            >
                                                                <div
                                                                    class="input"
                                                                    contenteditable="false"
                                                                    style="display: none;"
                                                                ></div>
                                                            </div>
                                                        </div>
                                                    `
                                                  : ""}`
                                        : html` ${{
                                              __html: render_user_custom_profile_fields({
                                                  profile_fields: context.profile_data,
                                              }),
                                          }}`}
                                </div>
                            </div>
                        </div>

                        <div class="tabcontent" id="user-profile-streams-tab">
                            <div class="alert stream_list_info"></div>
                            ${to_bool(context.show_user_subscribe_widget)
                                ? html` <div class="header-section">
                                          <h3 class="stream-tab-element-header">
                                              ${$t(
                                                  {
                                                      defaultMessage:
                                                          "Subscribe {full_name} to channels",
                                                  },
                                                  {full_name: context.full_name},
                                              )}
                                          </h3>
                                      </div>
                                      ${{__html: render_user_profile_subscribe_widget()}}`
                                : ""}
                            <div class="stream-list-top-section">
                                <div class="header-section">
                                    <h3 class="stream-tab-element-header">
                                        ${$t({defaultMessage: "Subscribed channels"})}
                                    </h3>
                                </div>
                                <input
                                    type="text"
                                    class="stream-search modal_text_input"
                                    placeholder="${$t({defaultMessage: "Filter channels"})}"
                                />
                                <button
                                    type="button"
                                    class="clear_search_button"
                                    id="clear_stream_search"
                                >
                                    <i class="fa fa-remove" aria-hidden="true"></i>
                                </button>
                            </div>
                            <div class="subscription-stream-list empty-list">
                                <table
                                    class="user-stream-list"
                                    data-empty="${$t({
                                        defaultMessage: "No channel subscriptions.",
                                    })}"
                                    data-search-results-empty="${$t({
                                        defaultMessage: "No matching channels",
                                    })}"
                                ></table>
                            </div>
                        </div>

                        <div class="tabcontent" id="user-profile-groups-tab">
                            <div class="subscription-group-list empty-list">
                                <table
                                    class="user-group-list"
                                    data-empty="${$t({
                                        defaultMessage: "No user group subscriptions.",
                                    })}"
                                ></table>
                            </div>
                        </div>
                        <div class="tabcontent" id="manage-profile-tab"></div>
                    </div>
                </main>
                <div class="manage-profile-tab-footer">
                    <footer class="modal__footer">
                        <div class="save-success"></div>
                        <button
                            type="button"
                            class="modal__button dialog_exit_button"
                            aria-label="${$t({defaultMessage: "Close this dialog window"})}"
                            data-micromodal-close
                        >
                            ${$t({defaultMessage: "Cancel"})}
                        </button>
                        <button type="button" class="modal__button dialog_submit_button">
                            <span class="submit-button-text"
                                >${$t({defaultMessage: "Save changes"})}</span
                            >
                            <div class="modal__spinner"></div>
                        </button>
                    </footer>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
