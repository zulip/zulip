import {html, to_html} from "../../shared/src/html.ts";
import {to_array, to_bool} from "../../src/hbs_compat.ts";
import {$t} from "../../src/i18n.ts";
import render_dropdown_widget_with_label from "../dropdown_widget_with_label.ts";
import render_help_link_widget from "../help_link_widget.ts";
import render_dropdown_options_widget from "./dropdown_options_widget.ts";
import render_group_setting_value_pill_input from "./group_setting_value_pill_input.ts";
import render_settings_checkbox from "./settings_checkbox.ts";
import render_settings_save_discard_widget from "./settings_save_discard_widget.ts";
import render_upgrade_tip_widget from "./upgrade_tip_widget.ts";

export default function render_organization_permissions_admin(context) {
    const out = html`<div
        id="organization-permissions"
        data-name="organization-permissions"
        class="settings-section"
    >
        <form class="admin-realm-form org-permissions-form">
            <div id="org-join-settings" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Joining the organization"})}
                        <i
                            class="fa fa-info-circle settings-info-icon tippy-zulip-tooltip"
                            aria-hidden="true"
                            data-tippy-content="${$t({
                                defaultMessage: "Only owners can change these settings.",
                            })}"
                        ></i>
                    </h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "join-settings",
                        }),
                    }}
                </div>
                <div class="m-10 inline-block organization-permissions-parent">
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({
                                defaultMessage: "Who can send email invitations to new users",
                            }),
                            setting_name: "realm_can_invite_users_group",
                        }),
                    }}
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can create reusable invitation links"}),
                            setting_name: "realm_create_multiuse_invite_group",
                        }),
                    }}
                    <div class="input-group">
                        <label for="id_realm_org_join_restrictions" class="settings-field-label"
                            >${$t({defaultMessage: "Restrict email domains of new users"})}</label
                        >
                        <select
                            name="realm_org_join_restrictions"
                            id="id_realm_org_join_restrictions"
                            class="prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="string"
                        >
                            <option value="no_restriction">
                                ${$t({defaultMessage: "No restrictions"})}
                            </option>
                            <option value="no_disposable_email">
                                ${$t({defaultMessage: "Don’t allow disposable email addresses"})}
                            </option>
                            <option value="only_selected_domain">
                                ${$t({defaultMessage: "Restrict to a list of domains"})}
                            </option>
                        </select>
                        <div class="dependent-settings-block">
                            <p id="allowed_domains_label" class="inline-block"></p>
                            ${to_bool(context.is_owner)
                                ? html`
                                      <a id="show_realm_domains_modal" role="button"
                                          >${$t({defaultMessage: "[Configure]"})}</a
                                      >
                                  `
                                : ""}
                        </div>
                    </div>
                    <div class="input-group time-limit-setting">
                        <label for="id_realm_waiting_period_threshold" class="settings-field-label">
                            ${$t({
                                defaultMessage:
                                    "Waiting period before new members turn into full members",
                            })}
                            ${{
                                __html: render_help_link_widget({
                                    link: "/help/restrict-permissions-of-new-members",
                                }),
                            }}
                        </label>
                        <select
                            name="realm_waiting_period_threshold"
                            id="id_realm_waiting_period_threshold"
                            class="prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="time-limit"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.waiting_period_threshold_dropdown_values,
                                }),
                            }}
                        </select>
                        ${/* This setting is hidden unless `custom_period` */ ""}
                        <div class="dependent-settings-block">
                            <label
                                for="id_realm_waiting_period_threshold_custom_input"
                                class="inline-block"
                                >${$t({defaultMessage: "Waiting period (days)"})}:</label
                            >
                            <input
                                type="text"
                                id="id_realm_waiting_period_threshold_custom_input"
                                name="realm_waiting_period_threshold_custom_input"
                                class="time-limit-custom-input"
                                value="${context.realm_waiting_period_threshold}"
                            />
                        </div>
                    </div>
                </div>
            </div>

            <div id="org-stream-permissions" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Channel permissions"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "stream-permissions",
                        }),
                    }}
                </div>
                <div class="m-10 inline-block organization-permissions-parent">
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can create public channels"}),
                            setting_name: "realm_can_create_public_channel_group",
                        }),
                    }}
                    ${{__html: render_upgrade_tip_widget(context)}}
                    ${{
                        __html: render_settings_checkbox({
                            help_link: "/help/public-access-option",
                            is_disabled: context.disable_enable_spectator_access_setting,
                            label: context.admin_settings_label.realm_enable_spectator_access,
                            is_checked: context.realm_enable_spectator_access,
                            prefix: "id_",
                            setting_name: "realm_enable_spectator_access",
                        }),
                    }}
                    ${{
                        __html: render_dropdown_widget_with_label({
                            value_type: "number",
                            label: $t({defaultMessage: "Who can create web-public channels"}),
                            widget_name: "realm_can_create_web_public_channel_group",
                        }),
                    }}
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can create private channels"}),
                            setting_name: "realm_can_create_private_channel_group",
                        }),
                    }}
                    <div class="input-group">
                        <label for="id_realm_invite_to_stream_policy" class="settings-field-label"
                            >${$t({defaultMessage: "Who can add users to channels"})}</label
                        >
                        <select
                            name="realm_invite_to_stream_policy"
                            id="id_realm_invite_to_stream_policy"
                            class="prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="number"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.common_policy_values,
                                }),
                            }}
                        </select>
                    </div>
                    <div class="input-group">
                        <label for="id_realm_wildcard_mention_policy" class="settings-field-label"
                            >${$t({
                                defaultMessage:
                                    "Who can notify a large number of users with a wildcard mention",
                            })}
                            ${{
                                __html: render_help_link_widget({
                                    link: "/help/restrict-wildcard-mentions",
                                }),
                            }}
                        </label>
                        <select
                            name="realm_wildcard_mention_policy"
                            id="id_realm_wildcard_mention_policy"
                            class="prop-element settings_select bootstrap-focus-style"
                            data-setting-widget-type="number"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.wildcard_mention_policy_values,
                                }),
                            }}
                        </select>
                    </div>
                </div>
            </div>

            <div id="org-group-permissions" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Group permissions"})}
                        ${{__html: render_help_link_widget({link: "/help/manage-user-groups"})}}
                    </h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "group-permissions",
                        }),
                    }}
                </div>
                <div class="m-10 inline-block organization-permissions-parent">
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can administer all user groups"}),
                            setting_name: "realm_can_manage_all_groups",
                        }),
                    }}
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can create user groups"}),
                            setting_name: "realm_can_create_groups",
                        }),
                    }}
                </div>
            </div>

            <div id="org-direct-message-permissions" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Direct message permissions"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/restrict-direct-messages",
                            }),
                        }}
                    </h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "direct-message-permissions",
                        }),
                    }}
                </div>

                ${{
                    __html: render_group_setting_value_pill_input({
                        label: $t({
                            defaultMessage: "Who can authorize a direct message conversation",
                        }),
                        setting_name: "realm_direct_message_permission_group",
                    }),
                }}
                ${{
                    __html: render_group_setting_value_pill_input({
                        label: $t({defaultMessage: "Who can start a direct message conversation"}),
                        setting_name: "realm_direct_message_initiator_group",
                    }),
                }}
            </div>

            <div id="org-msg-editing" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Message editing"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/restrict-message-editing-and-deletion",
                            }),
                        }}
                    </h3>
                    ${{__html: render_settings_save_discard_widget({section_name: "msg-editing"})}}
                </div>
                <div class="inline-block organization-settings-parent">
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_allow_message_editing,
                            is_checked: context.realm_allow_message_editing,
                            prefix: "id_",
                            setting_name: "realm_allow_message_editing",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_allow_edit_history,
                            is_checked: context.realm_allow_edit_history,
                            prefix: "id_",
                            setting_name: "realm_allow_edit_history",
                        }),
                    }}
                    <div class="input-group time-limit-setting">
                        <label
                            for="id_realm_message_content_edit_limit_seconds"
                            class="settings-field-label"
                            >${$t({defaultMessage: "Time limit for editing messages"})}</label
                        >
                        <select
                            name="realm_message_content_edit_limit_seconds"
                            id="id_realm_message_content_edit_limit_seconds"
                            class="prop-element settings_select bootstrap-focus-style"
                            ${!to_bool(context.realm_allow_message_editing) ? "disabled" : ""}
                            data-setting-widget-type="time-limit"
                        >
                            ${to_array(context.msg_edit_limit_dropdown_values).map(
                                (value) => html`
                                    <option value="${value.value}">${value.text}</option>
                                `,
                            )}
                        </select>
                        <div class="dependent-settings-block">
                            <label
                                for="id_realm_message_content_edit_limit_minutes"
                                class="inline-block realm-time-limit-label"
                            >
                                ${$t({
                                    defaultMessage:
                                        "Duration editing is allowed after posting (minutes)",
                                })}:&nbsp;
                            </label>
                            <input
                                type="text"
                                id="id_realm_message_content_edit_limit_minutes"
                                name="realm_message_content_edit_limit_minutes"
                                class="time-limit-custom-input"
                                autocomplete="off"
                                value="${context.realm_message_content_edit_limit_minutes}"
                                ${!to_bool(context.realm_allow_message_editing) ? "disabled" : ""}
                            />
                        </div>
                    </div>
                </div>
            </div>

            <div id="org-moving-msgs" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Moving messages"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/restrict-moving-messages",
                            }),
                        }}
                    </h3>
                    ${{__html: render_settings_save_discard_widget({section_name: "moving-msgs"})}}
                </div>

                ${{
                    __html: render_group_setting_value_pill_input({
                        label: $t({defaultMessage: "Who can move messages to another topic"}),
                        setting_name: "realm_can_move_messages_between_topics_group",
                    }),
                }}
                <div class="input-group time-limit-setting">
                    <label
                        for="id_realm_move_messages_within_stream_limit_seconds"
                        class="settings-field-label"
                        >${$t({defaultMessage: "Time limit for editing topics"})}
                        <i
                            >(${$t({
                                defaultMessage: "does not apply to moderators and administrators",
                            })})</i
                        ></label
                    >
                    <select
                        name="realm_move_messages_within_stream_limit_seconds"
                        id="id_realm_move_messages_within_stream_limit_seconds"
                        class="prop-element settings_select"
                        data-setting-widget-type="time-limit"
                    >
                        ${to_array(context.msg_move_limit_dropdown_values).map(
                            (value) => html`
                                <option value="${value.value}">${value.text}</option>
                            `,
                        )}
                    </select>
                    <div class="dependent-settings-block">
                        <label
                            for="id_realm_move_messages_within_stream_limit_minutes"
                            class="inline-block realm-time-limit-label"
                        >
                            ${$t({
                                defaultMessage:
                                    "Duration editing is allowed after posting (minutes)",
                            })}:&nbsp;
                        </label>
                        <input
                            type="text"
                            id="id_realm_move_messages_within_stream_limit_minutes"
                            name="realm_move_messages_within_stream_limit_minutes"
                            class="time-limit-custom-input"
                            autocomplete="off"
                        />
                    </div>
                </div>

                ${{
                    __html: render_group_setting_value_pill_input({
                        label: $t({defaultMessage: "Who can move messages to another channel"}),
                        setting_name: "realm_can_move_messages_between_channels_group",
                    }),
                }}
                <div class="input-group time-limit-setting">
                    <label
                        for="id_realm_move_messages_between_streams_limit_seconds"
                        class="settings-field-label"
                        >${$t({defaultMessage: "Time limit for moving messages between channels"})}
                        <i
                            >(${$t({
                                defaultMessage: "does not apply to moderators and administrators",
                            })})</i
                        ></label
                    >
                    <select
                        name="realm_move_messages_between_streams_limit_seconds"
                        id="id_realm_move_messages_between_streams_limit_seconds"
                        class="prop-element bootstrap-focus-style settings_select"
                        data-setting-widget-type="time-limit"
                    >
                        ${to_array(context.msg_move_limit_dropdown_values).map(
                            (value) => html`
                                <option value="${value.value}">${value.text}</option>
                            `,
                        )}
                    </select>
                    <div class="dependent-settings-block">
                        <label
                            for="id_realm_move_messages_between_streams_limit_minutes"
                            class="inline-block realm-time-limit-label"
                        >
                            ${$t({
                                defaultMessage:
                                    "Duration editing is allowed after posting (minutes)",
                            })}:&nbsp;
                        </label>
                        <input
                            type="text"
                            id="id_realm_move_messages_between_streams_limit_minutes"
                            name="realm_move_messages_between_streams_limit_minutes"
                            class="time-limit-custom-input"
                            autocomplete="off"
                        />
                    </div>
                </div>
            </div>

            <div id="org-msg-deletion" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "Message deletion"})}
                        ${{__html: render_help_link_widget({link: "/help/delete-a-message"})}}
                    </h3>
                    ${{__html: render_settings_save_discard_widget({section_name: "msg-deletion"})}}
                </div>
                <div class="inline-block organization-settings-parent">
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can delete any message"}),
                            setting_name: "realm_can_delete_any_message_group",
                        }),
                    }}
                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can delete their own messages"}),
                            setting_name: "realm_can_delete_own_message_group",
                        }),
                    }}
                    <div class="input-group time-limit-setting">
                        <label
                            for="id_realm_message_content_delete_limit_seconds"
                            class="settings-field-label"
                        >
                            ${$t({defaultMessage: "Time limit for deleting messages"})}
                            <i
                                >(${$t({
                                    defaultMessage:
                                        "does not apply to users who can delete any message",
                                })})</i
                            >
                        </label>
                        <select
                            name="realm_message_content_delete_limit_seconds"
                            id="id_realm_message_content_delete_limit_seconds"
                            class="prop-element bootstrap-focus-style settings_select"
                            data-setting-widget-type="time-limit"
                        >
                            ${to_array(context.msg_delete_limit_dropdown_values).map(
                                (value) => html`
                                    <option value="${value.value}">${value.text}</option>
                                `,
                            )}
                        </select>
                        <div class="dependent-settings-block">
                            <label
                                for="id_realm_message_content_delete_limit_minutes"
                                class="inline-block realm-time-limit-label"
                            >
                                ${$t({
                                    defaultMessage:
                                        "Duration deletion is allowed after posting (minutes)",
                                })}:
                            </label>
                            <input
                                type="text"
                                id="id_realm_message_content_delete_limit_minutes"
                                name="realm_message_content_delete_limit_minutes"
                                class="time-limit-custom-input"
                                autocomplete="off"
                                value="${context.realm_message_content_delete_limit_minutes}"
                            />
                        </div>
                    </div>
                </div>
            </div>

            <div id="org-user-identity" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>
                        ${$t({defaultMessage: "User identity"})}
                        ${{
                            __html: render_help_link_widget({
                                link: "/help/restrict-name-and-email-changes",
                            }),
                        }}
                    </h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "user-identity",
                        }),
                    }}
                </div>
                <div class="inline-block organization-permissions-parent">
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_require_unique_names,
                            is_checked: context.realm_require_unique_names,
                            prefix: "id_",
                            setting_name: "realm_require_unique_names",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_name_changes_disabled,
                            is_checked: context.realm_name_changes_disabled,
                            prefix: "id_",
                            setting_name: "realm_name_changes_disabled",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_email_changes_disabled,
                            is_checked: context.realm_email_changes_disabled,
                            prefix: "id_",
                            setting_name: "realm_email_changes_disabled",
                        }),
                    }}
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_avatar_changes_disabled,
                            is_checked: context.realm_avatar_changes_disabled,
                            prefix: "id_",
                            setting_name: "realm_avatar_changes_disabled",
                        }),
                    }}
                </div>
            </div>

            <div id="org-guest-settings" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Guests"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "guest-settings",
                        }),
                    }}
                </div>

                <div class="inline-block organization-permissions-parent">
                    ${{
                        __html: render_settings_checkbox({
                            label: context.admin_settings_label.realm_enable_guest_user_indicator,
                            is_checked: context.realm_enable_guest_user_indicator,
                            prefix: "id_",
                            setting_name: "realm_enable_guest_user_indicator",
                        }),
                    }}
                    ${{
                        __html: render_dropdown_widget_with_label({
                            help_link:
                                "/help/guest-users#configure-whether-guests-can-see-all-other-users",
                            value_type: "number",
                            label: $t({
                                defaultMessage: "Who can view all other users in the organization",
                            }),
                            widget_name: "realm_can_access_all_users_group",
                        }),
                    }}
                </div>
            </div>

            <div id="org-other-permissions" class="settings-subsection-parent">
                <div class="subsection-header">
                    <h3>${$t({defaultMessage: "Other permissions"})}</h3>
                    ${{
                        __html: render_settings_save_discard_widget({
                            section_name: "other-permissions",
                        }),
                    }}
                </div>
                <div class="m-10 inline-block organization-permissions-parent">
                    <div class="input-group">
                        <label for="id_realm_bot_creation_policy" class="settings-field-label"
                            >${$t({defaultMessage: "Who can add bots"})}</label
                        >
                        <select
                            name="realm_bot_creation_policy"
                            class="setting-widget prop-element settings_select bootstrap-focus-style"
                            id="id_realm_bot_creation_policy"
                            data-setting-widget-type="number"
                        >
                            ${{
                                __html: render_dropdown_options_widget({
                                    option_values: context.bot_creation_policy_values,
                                }),
                            }}
                        </select>
                    </div>

                    ${{
                        __html: render_group_setting_value_pill_input({
                            label: $t({defaultMessage: "Who can add custom emoji"}),
                            setting_name: "realm_can_add_custom_emoji_group",
                        }),
                    }}
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
