import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_user_group_creation_form from "./user_group_creation_form.ts";

export default function render_user_group_settings_overlay(context) {
    const out = html`<div id="groups_overlay" class="overlay" data-overlay="group_subscriptions">
        <div class="flex overlay-content">
            <div class="user-groups-container overlay-container">
                <div class="user-groups-header">
                    <div class="fa fa-chevron-left"></div>
                    <span class="user-groups-title">${$t({defaultMessage: "User groups"})}</span>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                </div>
                <div class="left">
                    <div class="list-toggler-container">
                        <div id="add_new_user_group">
                            ${to_bool(context.can_create_user_groups)
                                ? html`
                                      <button
                                          class="create_user_group_button create_user_group_plus_button"
                                      >
                                          <span class="create_button_plus_sign">+</span>
                                      </button>
                                  `
                                : ""}
                            <div class="float-clear"></div>
                        </div>
                    </div>
                    <div class="input-append group_name_search_section" id="group_filter">
                        <input
                            type="text"
                            name="group_name"
                            id="search_group_name"
                            class="filter_text_input"
                            autocomplete="off"
                            placeholder="${$t({defaultMessage: "Filter groups"})}"
                            value=""
                        />
                        <button
                            type="button"
                            class="bootstrap-btn clear_search_button"
                            id="clear_search_group_name"
                        >
                            <i class="fa fa-remove" aria-hidden="true"></i>
                        </button>
                    </div>
                    <div class="no-groups-to-show">
                        <div class="your_groups_tab_empty_text">
                            <span class="settings-empty-option-text">
                                ${$t({defaultMessage: "You are not a member of any user groups."})}
                                <a href="#groups/all"
                                    >${$t({defaultMessage: "View all user groups"})}</a
                                >
                            </span>
                        </div>
                        <div class="all_groups_tab_empty_text">
                            <span class="settings-empty-option-text">
                                ${$t({
                                    defaultMessage:
                                        "There are no user groups you can view in this organization.",
                                })}
                                ${to_bool(context.can_create_user_groups)
                                    ? html`
                                          <a href="#groups/new"
                                              >${$t({defaultMessage: "Create a user group"})}</a
                                          >
                                      `
                                    : ""}
                            </span>
                        </div>
                    </div>
                    <div
                        class="user-groups-list"
                        data-simplebar
                        data-simplebar-tab-index="-1"
                    ></div>
                </div>
                <div class="right">
                    <div class="display-type">
                        <div id="user_group_settings_title" class="user-group-info-title">
                            ${$t({defaultMessage: "User group settings"})}
                        </div>
                    </div>
                    <div class="nothing-selected">
                        <div class="group-info-banner"></div>
                        <div class="create-group-button-container">
                            <button
                                type="button"
                                class="create_user_group_button animated-purple-button"
                                ${!to_bool(context.can_create_user_groups) ? "disabled" : ""}
                            >
                                ${$t({defaultMessage: "Create user group"})}
                            </button>
                            ${!to_bool(context.can_create_user_groups)
                                ? html`
                                      <span class="settings-empty-option-text">
                                          ${$t({
                                              defaultMessage:
                                                  "You do not have permission to create user groups.",
                                          })}
                                      </span>
                                  `
                                : ""}
                        </div>
                    </div>
                    <div
                        id="user_group_settings"
                        class="settings"
                        data-simplebar
                        data-simplebar-tab-index="-1"
                        data-simplebar-auto-hide="false"
                    >
                        ${/* edit user group here */ ""}
                    </div>
                    ${{__html: render_user_group_creation_form(context)}}
                </div>
            </div>
        </div>
    </div> `;
    return to_html(out);
}
