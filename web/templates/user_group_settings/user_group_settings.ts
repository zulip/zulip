import {to_bool} from "../../src/hbs_compat.ts";
import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_icon_button from "../components/icon_button.ts";
import render_creator_details from "../creator_details.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";
import render_group_permission_settings from "./group_permission_settings.ts";
import render_group_permissions from "./group_permissions.ts";
import render_user_group_members from "./user_group_members.ts";

export default function render_user_group_settings(context) {
    const out = html`<div class="group_settings_header" data-group-id="${context.group.id}">
            <div class="tab-container"></div>
            <div class="button-group">
                <div class="join_leave_button_wrapper inline-block">
                    ${to_bool(context.is_direct_member)
                        ? html` ${{
                              __html: render_action_button({
                                  intent: "neutral",
                                  attention: "quiet",
                                  type: "button",
                                  custom_classes: "join_leave_button",
                                  label: $t({defaultMessage: "Leave group"}),
                              }),
                          }}`
                        : html` ${{
                              __html: render_action_button({
                                  intent: "brand",
                                  attention: "quiet",
                                  type: "button",
                                  custom_classes: "join_leave_button",
                                  label: $t({defaultMessage: "Join group"}),
                              }),
                          }}`}
                </div>
                ${{
                    __html: render_icon_button({
                        ["data-tippy-content"]: $t({defaultMessage: "Deactivate group"}),
                        custom_classes:
                            "deactivate-group-button deactivate tippy-zulip-delayed-tooltip",
                        intent: "danger",
                        icon: "user-group-x",
                    }),
                }}
                ${{
                    __html: render_icon_button({
                        ["data-tippy-content"]: $t({defaultMessage: "Reactivate group"}),
                        custom_classes:
                            "reactivate-group-button reactivate tippy-zulip-delayed-tooltip",
                        intent: "success",
                        icon: "user-group-plus",
                    }),
                }}
            </div>
        </div>
        <div class="user_group_settings_wrapper" data-group-id="${context.group.id}">
            <div class="inner-box">
                <div
                    class="group_general_settings group_setting_section"
                    data-group-section="general"
                >
                    <div class="group-reactivation-error-banner"></div>
                    <div class="group-banner"></div>
                    <div class="group-header">
                        <div class="group-name-wrapper">
                            <span class="group-name" data-tippy-content="${context.group.name}"
                                >${context.group.name}</span
                            >
                        </div>
                        <div class="group_change_property_info alert-notification"></div>
                        <div class="button-group">
                            ${{
                                __html: render_icon_button({
                                    id: "open_group_info_modal",
                                    ["data-tippy-content"]: $t({
                                        defaultMessage: "Change group info",
                                    }),
                                    custom_classes: "tippy-zulip-delayed-tooltip",
                                    intent: "neutral",
                                    icon: "user-group-edit",
                                }),
                            }}
                        </div>
                    </div>
                    <div class="group-description-wrapper">
                        <span class="group-description"> ${context.group.description} </span>
                    </div>

                    <div class="creator_details group_detail_box">
                        ${{
                            __html: render_creator_details({
                                group_id: context.group.id,
                                ...context,
                            }),
                        }}
                    </div>

                    <div
                        class="group-permissions settings-subsection-parent"
                        id="group_permission_settings"
                    >
                        <div class="subsection-header">
                            <h3 class="user_group_setting_subsection_title">
                                ${$t({defaultMessage: "Group permissions"})}
                                ${{
                                    __html: render_help_link_widget({
                                        link: "/help/manage-user-groups#configure-group-permissions",
                                    }),
                                }}
                            </h3>
                            ${{
                                __html: render_settings_save_discard_widget({
                                    section_name: "group-permissions",
                                }),
                            }}
                        </div>

                        ${{
                            __html: render_group_permissions({
                                group_setting_labels: context.all_group_setting_labels.group,
                                prefix: "id_",
                            }),
                        }}
                    </div>
                </div>

                <div
                    class="group_member_settings group_setting_section"
                    data-group-section="members"
                >
                    <div class="edit_members_for_user_group">
                        ${{__html: render_user_group_members(context)}}
                    </div>
                </div>

                <div class="group_setting_section" data-group-section="permissions">
                    <div class="group-assigned-permissions">
                        <span
                            class="no-permissions-for-group-text ${!to_bool(
                                context.group_has_no_permissions,
                            )
                                ? "hide"
                                : ""}"
                        >
                            ${$t({defaultMessage: "This group has no assigned permissions."})}
                        </span>
                        ${{__html: render_group_permission_settings(context)}}
                    </div>
                </div>
            </div>
        </div> `;
    return to_html(out);
}
