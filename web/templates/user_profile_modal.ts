import {to_bool} from "../src/hbs_compat.ts";
import {html, to_html} from "../src/html.ts";
import {$t} from "../src/i18n.ts";
import render_action_button from "./components/action_button.ts";
import render_icon_button from "./components/icon_button.ts";
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
                                      <span
                                          class="tippy-zulip-tooltip user-status-icon-wrapper"
                                          data-tippy-content="${context.last_seen}"
                                      >
                                          <span
                                              class="zulip-icon zulip-icon-${context.user_circle_class} ${context.user_circle_class} user-circle user_profile_presence"
                                              data-presence-indicator-user-id="${context.user_id}"
                                          ></span>
                                      </span>
                                  `
                                : html`
                                      <span>
                                          <i
                                              class="fa fa-ban deactivated-user-icon tippy-zulip-tooltip"
                                              data-tippy-content="Deactivated user"
                                          ></i>
                                      </span>
                                  `
                            : ""}${to_bool(context.is_bot)
                            ? html` <i class="zulip-icon zulip-icon-bot" aria-hidden="true"></i> `
                            : ""}
                        <span class="user-profile-name"
                            >${{__html: render_user_full_name({name: context.full_name})}}</span
                        >
                        <span class="user-profile-header-actions">
                            ${{
                                __html: render_icon_button({
                                    ["aria-label"]: $t({defaultMessage: "Copy link to profile"}),
                                    ["data-tippy-content"]: $t({
                                        defaultMessage: "Copy link to profile",
                                    }),
                                    intent: "neutral",
                                    icon: "link-alt",
                                    custom_classes:
                                        "copy-link-to-user-profile tippy-zulip-delayed-tooltip",
                                }),
                            }}${to_bool(context.is_me)
                                ? to_bool(context.can_manage_profile)
                                    ? html` ${{
                                          __html: render_icon_button({
                                              ["aria-label"]: $t({defaultMessage: "Edit profile"}),
                                              ["data-tippy-content"]: $t({
                                                  defaultMessage: "Edit profile",
                                              }),
                                              intent: "neutral",
                                              icon: "edit",
                                              custom_classes:
                                                  "user-profile-update-user-tab-button tippy-zulip-delayed-tooltip",
                                          }),
                                      }}`
                                    : html` ${{
                                          __html: render_icon_button({
                                              ["aria-label"]: $t({defaultMessage: "Edit profile"}),
                                              ["data-tippy-content"]: $t({
                                                  defaultMessage: "Edit profile",
                                              }),
                                              intent: "neutral",
                                              icon: "edit",
                                              custom_classes:
                                                  "user-profile-profile-settings-button tippy-zulip-delayed-tooltip",
                                          }),
                                      }}`
                                : to_bool(context.can_manage_profile)
                                  ? html`${to_bool(context.is_bot)
                                        ? html` ${{
                                              __html: render_icon_button({
                                                  ["aria-label"]: $t({
                                                      defaultMessage: "Manage bot",
                                                  }),
                                                  ["data-tippy-content"]: $t({
                                                      defaultMessage: "Manage bot",
                                                  }),
                                                  intent: "neutral",
                                                  icon: "edit",
                                                  custom_classes:
                                                      "user-profile-update-user-tab-button tippy-zulip-delayed-tooltip",
                                              }),
                                          }}`
                                        : html` ${{
                                              __html: render_icon_button({
                                                  ["aria-label"]: $t({
                                                      defaultMessage: "Manage user",
                                                  }),
                                                  ["data-tippy-content"]: $t({
                                                      defaultMessage: "Manage user",
                                                  }),
                                                  intent: "neutral",
                                                  icon: "edit",
                                                  custom_classes:
                                                      "user-profile-update-user-tab-button tippy-zulip-delayed-tooltip",
                                              }),
                                          }}`} `
                                  : ""}
                        </span>
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
                            <div class="stream-list-top-section">
                                <div class="header-section">
                                    <h3 class="stream-tab-element-header">
                                        ${$t({defaultMessage: "Subscribed channels"})}
                                    </h3>
                                </div>
                                <div class="stream-list-container">
                                    <div
                                        class="stream-search-container filter-input has-input-icon has-input-button input-element-wrapper"
                                    >
                                        <i
                                            class="input-icon zulip-icon zulip-icon-search"
                                            aria-hidden="true"
                                        ></i>
                                        <input
                                            type="text"
                                            class="input-element stream-search"
                                            placeholder="${$t({defaultMessage: "Filter"})}"
                                        />
                                        <button
                                            type="button"
                                            class="input-button input-close-filter-button icon-button icon-button-square icon-button-neutral"
                                        >
                                            <i
                                                class="zulip-icon zulip-icon-close"
                                                aria-hidden="true"
                                            ></i>
                                        </button>
                                    </div>
                                    <div class="stream-list-loader"></div>
                                    <div
                                        class="subscription-stream-list"
                                        data-simplebar
                                        data-simplebar-tab-index="-1"
                                    >
                                        <ul
                                            class="user-stream-list"
                                            data-empty="${$t({
                                                defaultMessage: "No channel subscriptions.",
                                            })}"
                                            data-search-results-empty="${$t({
                                                defaultMessage: "No matching channels.",
                                            })}"
                                        ></ul>
                                    </div>
                                </div>
                            </div>
                            <div class="stream-list-bottom-section">
                                <div class="header-section">
                                    <h3 class="stream-tab-element-header">
                                        ${$t(
                                            {defaultMessage: "Subscribe {full_name} to channels"},
                                            {full_name: context.full_name},
                                        )}
                                    </h3>
                                </div>
                                ${{__html: render_user_profile_subscribe_widget()}}
                            </div>
                        </div>

                        <div class="tabcontent" id="user-profile-groups-tab">
                            <div class="alert user-profile-group-list-alert"></div>
                            <div class="group-list-top-section">
                                <div class="header-section">
                                    <h3 class="group-tab-element-header">
                                        ${$t({defaultMessage: "Group membership"})}
                                    </h3>
                                </div>
                                <div class="group-list-container">
                                    <div
                                        class="group-search-container filter-input has-input-icon has-input-button input-element-wrapper"
                                    >
                                        <i class="input-icon zulip-icon zulip-icon-search"></i>
                                        <input
                                            type="text"
                                            class="input-element group-search"
                                            placeholder="${$t({defaultMessage: "Filter"})}"
                                        />
                                        <button
                                            type="button"
                                            class="input-button input-close-filter-button icon-button icon-button-square icon-button-neutral"
                                        >
                                            <i
                                                class="zulip-icon zulip-icon-close"
                                                aria-hidden="true"
                                            ></i>
                                        </button>
                                    </div>
                                    <div
                                        class="subscription-group-list"
                                        data-simplebar
                                        data-simplebar-tab-index="-1"
                                    >
                                        <ul
                                            class="user-group-list"
                                            data-empty="${$t({
                                                defaultMessage: "Not a member of any groups.",
                                            })}"
                                            data-search-results-empty="${$t({
                                                defaultMessage: "No matching user groups",
                                            })}"
                                        ></ul>
                                    </div>
                                </div>
                            </div>
                            <div class="group-list-bottom-section">
                                <div class="header-section">
                                    <h3 class="group-tab-element-header">
                                        ${$t(
                                            {defaultMessage: "Add {full_name} to groups"},
                                            {full_name: context.full_name},
                                        )}
                                    </h3>
                                </div>
                                <div id="groups-to-add" class="add-button-container">
                                    <div id="user-group-to-add">
                                        <div class="add-user-group-container">
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
                                    ${{
                                        __html: render_action_button({
                                            ["aria-label"]: $t({defaultMessage: "Add"}),
                                            intent: "brand",
                                            attention: "quiet",
                                            custom_classes: "add-groups-button",
                                            label: $t({defaultMessage: "Add"}),
                                        }),
                                    }}
                                </div>
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
                            <span class="modal__spinner"></span>
                        </button>
                    </footer>
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
