import {html, to_html} from "../../shared/src/html.ts";
import {to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_creator_details from "../creator_details.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_settings_save_discard_widget from "../settings/settings_save_discard_widget.ts";
import render_group_permissions from "./group_permissions.ts";
import render_user_group_members from "./user_group_members.ts";

export default function render_user_group_settings(context) {
    const out = html`<div class="group_settings_header" data-group-id="${context.group.id}">
            <div class="tab-container"></div>
            <div class="button-group">
                <div class="join_leave_button_wrapper inline-block">
                    <button
                        class="button small rounded join_leave_button"
                        type="button"
                        name="button"
                    >
                        ${to_bool(context.is_member)
                            ? html` ${$t({defaultMessage: "Leave group"})} `
                            : html` ${$t({defaultMessage: "Join group"})} `}
                    </button>
                </div>
                <button
                    class="button small rounded button-danger deactivate tippy-zulip-delayed-tooltip"
                    data-tippy-content="${$t({defaultMessage: "Deactivate group"})}"
                    type="button"
                    name="delete_button"
                >
                    <i class="fa fa-trash-o" aria-hidden="true"></i>
                </button>
            </div>
        </div>
        <div class="user_group_settings_wrapper" data-group-id="${context.group.id}">
            <div class="inner-box">
                <div
                    class="group_general_settings group_setting_section"
                    data-group-section="general"
                >
                    <div class="group-header">
                        <div class="group-name-wrapper">
                            <span class="group-name" title="${context.group.name}"
                                >${context.group.name}</span
                            >
                        </div>
                        <div class="group_change_property_info alert-notification"></div>
                        <div class="button-group">
                            <button
                                id="open_group_info_modal"
                                class="button rounded small button-warning tippy-zulip-delayed-tooltip"
                                data-tippy-content="${$t({defaultMessage: "Change group info"})}"
                            >
                                <i class="fa fa-pencil" aria-hidden="true"></i>
                            </button>
                        </div>
                    </div>
                    <div class="group-description-wrapper">
                        <span class="group-description"> ${context.group.description} </span>
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

                        ${{__html: render_group_permissions({prefix: "id_"})}}
                    </div>

                    <div class="group_detail_box">
                        <div class="user_group_details_box_header">
                            <h3 class="user_group_setting_subsection_title">
                                ${$t({defaultMessage: "User group details"})}
                            </h3>
                        </div>
                        <div class="creator_details group_details_box_subsection">
                            ${{__html: render_creator_details(context)}}
                        </div>
                        <div class="group_details_box_subsection">
                            ${$t({defaultMessage: "User group ID"})}<br />
                            ${context.group.id}
                        </div>
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
            </div>
        </div> `;
    return to_html(out);
}
