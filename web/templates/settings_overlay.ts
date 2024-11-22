import {html, to_html} from "../shared/src/html.ts";
import {to_bool} from "../src/hbs_compat.ts";
import {$t} from "../src/i18n.ts";

export default function render_settings_overlay(context) {
    const out = html`<div id="settings_page" class="overlay-content overlay-container">
        <div class="settings-header mobile">
            <i class="fa fa-chevron-left" aria-hidden="true"></i>
            <h1>${$t({defaultMessage: "Settings"})}<span class="section"></span></h1>
            <div class="exit">
                <span class="exit-sign">&times;</span>
            </div>
            <div class="clear-float"></div>
        </div>
        <div class="sidebar-wrapper">
            <div class="tab-container"></div>
            <div class="sidebar left" data-simplebar data-simplebar-tab-index="-1">
                <div class="sidebar-list dark-grey small-text">
                    <ul class="normal-settings-list">
                        <li class="sidebar-item" tabindex="0" data-section="profile">
                            <i class="sidebar-item-icon fa fa-user" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Profile"})}</div>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="account-and-privacy">
                            <i class="sidebar-item-icon fa fa-lock" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Account & privacy"})}</div>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="preferences">
                            <i class="sidebar-item-icon fa fa-sliders" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Preferences"})}</div>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="notifications">
                            <i
                                class="sidebar-item-icon fa fa-exclamation-triangle"
                                aria-hidden="true"
                            ></i>
                            <div class="text">${$t({defaultMessage: "Notifications"})}</div>
                        </li>
                        ${!to_bool(context.is_guest)
                            ? html`
                                  <li class="sidebar-item" tabindex="0" data-section="your-bots">
                                      <i
                                          class="sidebar-item-icon zulip-icon zulip-icon-bot"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">${$t({defaultMessage: "Bots"})}</div>
                                  </li>
                              `
                            : ""}
                        <li class="sidebar-item" tabindex="0" data-section="alert-words">
                            <i class="sidebar-item-icon fa fa-book" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Alert words"})}</div>
                        </li>
                        ${to_bool(context.show_uploaded_files_section)
                            ? html`
                                  <li
                                      class="sidebar-item"
                                      tabindex="0"
                                      data-section="uploaded-files"
                                  >
                                      <i
                                          class="sidebar-item-icon fa fa-paperclip"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">
                                          ${$t({defaultMessage: "Uploaded files"})}
                                      </div>
                                  </li>
                              `
                            : ""}
                        <li class="sidebar-item" tabindex="0" data-section="topics">
                            <i
                                class="sidebar-item-icon zulip-icon zulip-icon-topic"
                                aria-hidden="true"
                            ></i>
                            <div class="text">${$t({defaultMessage: "Topics"})}</div>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="muted-users">
                            <i class="sidebar-item-icon fa fa-eye-slash" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Muted users"})}</div>
                        </li>
                    </ul>

                    <ul class="org-settings-list">
                        <li class="sidebar-item" tabindex="0" data-section="organization-profile">
                            <i class="sidebar-item-icon fa fa-id-card" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Organization profile"})}</div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_admin) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization administrators can edit these settings.",
                                })}"
                            ></i>
                        </li>
                        <li
                            class="sidebar-item"
                            class="collapse-org-settings ${!to_bool(context.is_admin)
                                ? "hide-org-settings"
                                : ""}"
                            tabindex="0"
                            data-section="organization-settings"
                        >
                            <i class="sidebar-item-icon fa fa-sliders" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Organization settings"})}</div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_admin) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization administrators can edit these settings",
                                })}"
                            ></i>
                        </li>
                        <li
                            class="sidebar-item"
                            class="collapse-org-settings ${!to_bool(context.is_admin)
                                ? "hide-org-settings"
                                : ""}"
                            tabindex="0"
                            data-section="organization-permissions"
                        >
                            <i class="sidebar-item-icon fa fa-lock" aria-hidden="true"></i>
                            <div class="text">
                                ${$t({defaultMessage: "Organization permissions"})}
                            </div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_admin) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization administrators can edit these settings.",
                                })}"
                            ></i>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="emoji-settings">
                            <i class="sidebar-item-icon fa fa-smile-o" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Custom emoji"})}</div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${!to_bool(context.show_emoji_settings_lock)
                                    ? html`style="display: none;"`
                                    : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "You do not have permission to add custom emoji.",
                                })}"
                            ></i>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="linkifier-settings">
                            <i class="sidebar-item-icon fa fa-font" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Linkifiers"})}</div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_admin) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization administrators can edit these settings.",
                                })}"
                            ></i>
                        </li>
                        <li class="sidebar-item" tabindex="0" data-section="playground-settings">
                            <i class="sidebar-item-icon fa fa-external-link" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Code playgrounds"})}</div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_admin) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization administrators can edit these settings.",
                                })}"
                            ></i>
                        </li>
                        ${!to_bool(context.is_guest)
                            ? html`
                                  <li class="sidebar-item" tabindex="0" data-section="users">
                                      <i
                                          class="sidebar-item-icon fa fa-user"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">${$t({defaultMessage: "Users"})}</div>
                                      <i
                                          class="locked fa fa-lock tippy-zulip-tooltip"
                                          ${to_bool(context.can_edit_user_panel)
                                              ? html`style="display: none;"`
                                              : ""}
                                          data-tippy-content="${$t({
                                              defaultMessage:
                                                  "Only organization administrators can edit these settings.",
                                          })}"
                                      ></i>
                                  </li>
                              `
                            : ""}${!to_bool(context.is_guest)
                            ? html`
                                  <li
                                      class="sidebar-item"
                                      tabindex="0"
                                      data-section="bot-list-admin"
                                  >
                                      <i
                                          class="sidebar-item-icon zulip-icon zulip-icon-bot"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">${$t({defaultMessage: "Bots"})}</div>
                                      <i
                                          class="locked fa fa-lock tippy-zulip-tooltip"
                                          ${to_bool(context.can_create_new_bots)
                                              ? html`style="display: none;"`
                                              : ""}
                                          data-tippy-content="${$t({
                                              defaultMessage:
                                                  "Only organization administrators can edit these settings.",
                                          })}"
                                      ></i>
                                  </li>
                              `
                            : ""}${to_bool(context.is_admin)
                            ? html`
                                  <li
                                      class="sidebar-item"
                                      tabindex="0"
                                      data-section="profile-field-settings"
                                  >
                                      <i
                                          class="sidebar-item-icon fa fa-id-card"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">
                                          ${$t({defaultMessage: "Custom profile fields"})}
                                      </div>
                                  </li>
                              `
                            : ""}
                        <li
                            class="sidebar-item collapse-org-settings ${!to_bool(context.is_admin)
                                ? "hide-org-settings"
                                : ""}"
                            tabindex="0"
                            data-section="organization-level-user-defaults"
                        >
                            <i class="sidebar-item-icon fa fa-cog" aria-hidden="true"></i>
                            <div class="text">${$t({defaultMessage: "Default user settings"})}</div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_admin) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization administrators can edit these settings.",
                                })}"
                            ></i>
                        </li>
                        ${!to_bool(context.is_guest)
                            ? html`
                                  <li
                                      class="sidebar-item collapse-org-settings ${!to_bool(
                                          context.is_admin,
                                      )
                                          ? "hide-org-settings"
                                          : ""}"
                                      tabindex="0"
                                      data-section="default-channels-list"
                                  >
                                      <i
                                          class="sidebar-item-icon fa fa-exchange"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">
                                          ${$t({defaultMessage: "Default channels"})}
                                      </div>
                                      ${!to_bool(context.is_admin)
                                          ? html`
                                                <i
                                                    class="locked fa fa-lock tippy-zulip-tooltip"
                                                    data-tippy-content="${$t({
                                                        defaultMessage:
                                                            "Only organization administrators can edit these settings.",
                                                    })}"
                                                ></i>
                                            `
                                          : ""}
                                  </li>
                              `
                            : ""}
                        <li
                            class="sidebar-item collapse-org-settings ${!to_bool(context.is_admin)
                                ? "hide-org-settings"
                                : ""}"
                            tabindex="0"
                            data-section="auth-methods"
                        >
                            <i class="sidebar-item-icon fa fa-key" aria-hidden="true"></i>
                            <div class="text">
                                ${$t({defaultMessage: "Authentication methods"})}
                            </div>
                            <i
                                class="locked fa fa-lock tippy-zulip-tooltip"
                                ${to_bool(context.is_owner) ? html`style="display: none;"` : ""}
                                data-tippy-content="${$t({
                                    defaultMessage:
                                        "Only organization owners can edit these settings.",
                                })}"
                            ></i>
                        </li>
                        ${to_bool(context.is_admin)
                            ? html`
                                  <li
                                      class="sidebar-item"
                                      tabindex="0"
                                      data-section="data-exports-admin"
                                  >
                                      <i
                                          class="sidebar-item-icon fa fa-database"
                                          aria-hidden="true"
                                      ></i>
                                      <div class="text">
                                          ${$t({defaultMessage: "Data exports"})}
                                      </div>
                                  </li>
                              `
                            : ""}${!to_bool(context.is_admin)
                            ? html`
                                  <li class="sidebar-item collapse-settings-button">
                                      <i
                                          id="toggle_collapse_chevron"
                                          class="sidebar-item-icon fa fa-angle-double-down"
                                      ></i>
                                      <div class="text" id="toggle_collapse">
                                          ${$t({defaultMessage: "Show more"})}
                                      </div>
                                  </li>
                              `
                            : ""}
                    </ul>
                </div>
            </div>
        </div>
        <div class="content-wrapper right">
            <div class="settings-header">
                <h1>${$t({defaultMessage: "Settings"})}<span class="section"></span></h1>
                <div class="exit">
                    <span class="exit-sign">&times;</span>
                </div>
            </div>
            <div
                id="settings_content"
                data-simplebar
                data-simplebar-tab-index="-1"
                data-simplebar-auto-hide="false"
            >
                <div class="organization-box organization"></div>
                <div class="settings-box"></div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
