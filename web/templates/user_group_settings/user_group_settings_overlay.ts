import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget from "../dropdown_widget.ts";
import render_upgrade_tip_widget from "../settings/upgrade_tip_widget.ts";
import render_user_group_creation_form from "./user_group_creation_form.ts";

export default function render_user_group_settings_overlay(context) {
    const out = html`<div
        id="groups_overlay"
        class="two-pane-settings-overlay overlay"
        data-overlay="group_subscriptions"
    >
        <div class="flex overlay-content">
            <div class="two-pane-settings-container overlay-container">
                <div class="two-pane-settings-header">
                    <div class="fa fa-chevron-left"></div>
                    <span class="user-groups-title">${$t({defaultMessage: "User groups"})}</span>
                    <div class="exit">
                        <span class="exit-sign">&times;</span>
                    </div>
                </div>
                <div class="two-pane-settings-content">
                    <div class="left">
                        <div class="two-pane-settings-subheader">
                            <div class="list-toggler-container">
                                <div id="add_new_user_group">
                                    <button
                                        class="create_user_group_button two-pane-settings-plus-button"
                                    >
                                        <i
                                            class="create_button_plus_sign zulip-icon zulip-icon-user-group-plus"
                                            aria-hidden="true"
                                        ></i>
                                    </button>
                                    <div class="float-clear"></div>
                                </div>
                            </div>
                        </div>
                        <div class="two-pane-settings-body">
                            <div
                                class="input-append group_name_search_section two-pane-settings-search"
                                id="group_filter"
                            >
                                <input
                                    type="text"
                                    name="group_name"
                                    id="search_group_name"
                                    class="filter_text_input"
                                    autocomplete="off"
                                    placeholder="${$t({defaultMessage: "Filter"})}"
                                    value=""
                                />
                                <button
                                    type="button"
                                    class="clear_search_button"
                                    id="clear_search_group_name"
                                >
                                    <i class="zulip-icon zulip-icon-close" aria-hidden="true"></i>
                                </button>
                                <span>
                                    <label class="checkbox" id="user-group-edit-filter-options">
                                        ${{
                                            __html: render_dropdown_widget({
                                                widget_name: "user_group_visibility_settings",
                                            }),
                                        }}
                                    </label>
                                </span>
                            </div>
                            <div class="no-groups-to-show"></div>
                            <div
                                class="user-groups-list-wrapper two-pane-settings-left-simplebar-container"
                                data-simplebar
                                data-simplebar-tab-index="-1"
                            >
                                <div class="user-groups-list"></div>
                            </div>
                        </div>
                    </div>
                    <div class="right">
                        <div class="two-pane-settings-subheader">
                            <div class="display-type">
                                <div id="user_group_settings_title" class="user-group-info-title">
                                    ${$t({defaultMessage: "User group settings"})}
                                </div>
                                <i
                                    class="fa fa-ban deactivated-user-icon deactivated-user-group-icon-right"
                                ></i>
                            </div>
                        </div>
                        <div class="two-pane-settings-body">
                            <div class="nothing-selected">
                                <div class="group-info-banner banner-wrapper"></div>
                                <div class="create-group-button-container">
                                    ${{__html: render_upgrade_tip_widget(context)}}
                                    <button
                                        type="button"
                                        class="create_user_group_button animated-purple-button"
                                    >
                                        ${$t({defaultMessage: "Create user group"})}
                                    </button>
                                    <span
                                        class="settings-empty-option-text creation-permission-text"
                                    >
                                        ${$t({
                                            defaultMessage:
                                                "You do not have permission to create user groups.",
                                        })}
                                    </span>
                                </div>
                            </div>
                            <div
                                id="user_group_settings"
                                class="two-pane-settings-right-simplebar-container settings"
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
            </div>
        </div>
    </div> `;
    return to_html(out);
}
