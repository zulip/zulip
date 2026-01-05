import {html, to_html} from "../../src/html.ts";
import {$t} from "../../src/i18n.ts";
import render_action_button from "../components/action_button.ts";
import render_group_permissions from "./group_permissions.ts";

export default function render_user_group_creation_form(context) {
    const out = html`<div
        class="hide two-pane-settings-right-simplebar-container"
        id="user-group-creation"
        tabindex="-1"
        role="dialog"
        aria-label="${$t({defaultMessage: "User group creation"})}"
    >
        <form id="user_group_creation_form">
            <div
                class="two-pane-settings-creation-simplebar-container"
                data-simplebar
                data-simplebar-tab-index="-1"
            >
                <div class="alert user_group_create_info"></div>
                <div id="user_group_creating_indicator"></div>
                <div class="user-group-creation-body">
                    <div class="configure_user_group_settings user_group_creation">
                        <section id="user-group-name-container">
                            <label for="create_user_group_name" class="settings-field-label">
                                ${$t({defaultMessage: "User group name"})}
                            </label>
                            <input
                                type="text"
                                name="user_group_name"
                                id="create_user_group_name"
                                class="settings_text_input"
                                placeholder="${$t({defaultMessage: "User group name"})}"
                                value=""
                                autocomplete="off"
                                maxlength="${context.max_user_group_name_length}"
                            />
                            <div id="user_group_name_error" class="user_group_creation_error"></div>
                            <a id="deactivated_group_rename"></a>
                        </section>
                        <section id="user-group-description-container">
                            <label for="create_user_group_description" class="settings-field-label">
                                ${$t({defaultMessage: "User group description"})}
                            </label>
                            <input
                                type="text"
                                name="user_group_description"
                                id="create_user_group_description"
                                class="settings_text_input"
                                placeholder="${$t({defaultMessage: "User group description"})}"
                                value=""
                                autocomplete="off"
                            />
                        </section>
                        <section id="user-group-permission-container">
                            <div
                                class="group-permissions settings-subsection-parent"
                                id="new_group_permission_settings"
                            >
                                <div class="subsection-header">
                                    <h3 class="user_group_setting_subsection_title">
                                        ${$t({defaultMessage: "Group permissions"})}
                                    </h3>
                                </div>

                                ${{
                                    __html: render_group_permissions({
                                        group_setting_labels:
                                            context.all_group_setting_labels.group,
                                        prefix: "id_new_group_",
                                    }),
                                }}
                            </div>
                        </section>
                    </div>
                    <div class="user_group_members_container user_group_creation">
                        <section id="choose_member_section">
                            <h4 class="user_group_setting_subsection_title">
                                <label for="people_to_add_in_group"
                                    >${$t({defaultMessage: "Choose members"})}</label
                                >
                            </h4>
                            <div
                                id="user_group_membership_error"
                                class="user_group_creation_error"
                            ></div>
                            <div class="controls" id="people_to_add_in_group"></div>
                        </section>
                    </div>
                </div>
            </div>
            <div class="settings-sticky-footer">
                <div class="settings-sticky-footer-left">
                    ${{
                        __html: render_action_button({
                            id: "user_group_go_to_configure_settings",
                            intent: "brand",
                            attention: "quiet",
                            custom_classes: "hide",
                            label: $t({defaultMessage: "Back to settings"}),
                        }),
                    }}
                </div>
                <div class="settings-sticky-footer-right">
                    ${{
                        __html: render_action_button({
                            intent: "neutral",
                            attention: "quiet",
                            custom_classes: "create_user_group_cancel inline-block",
                            label: $t({defaultMessage: "Cancel"}),
                        }),
                    }}
                    ${{
                        __html: render_action_button({
                            type: "submit",
                            intent: "brand",
                            attention: "quiet",
                            custom_classes: "finalize_create_user_group hide",
                            label: $t({defaultMessage: "Create"}),
                        }),
                    }}
                    ${{
                        __html: render_action_button({
                            intent: "brand",
                            attention: "quiet",
                            custom_classes: "inline-block",
                            id: "user_group_go_to_members",
                            label: $t({defaultMessage: "Continue to add members"}),
                        }),
                    }}
                </div>
            </div>
        </form>
    </div> `;
    return to_html(out);
}
