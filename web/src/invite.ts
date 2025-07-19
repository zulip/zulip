import ClipboardJS from "clipboard";
import {add} from "date-fns";
import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_copy_invite_link from "../templates/copy_invite_link.hbs";
import render_invitation_failed_error from "../templates/invitation_failed_error.hbs";
import render_invite_user_modal from "../templates/invite_user_modal.hbs";
import render_invite_tips_banner from "../templates/modal_banner/invite_tips_banner.hbs";
import render_settings_dev_env_email_access from "../templates/settings/dev_env_email_access.hbs";

import * as channel from "./channel.ts";
import * as common from "./common.ts";
import * as components from "./components.ts";
import * as compose_banner from "./compose_banner.ts";
import {show_copied_confirmation} from "./copied_tooltip.ts";
import {csrf_token} from "./csrf.ts";
import * as demo_organizations_ui from "./demo_organizations_ui.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as email_pill from "./email_pill.ts";
import {$t, $t_html} from "./i18n.ts";
import * as invite_stream_picker_pill from "./invite_stream_picker_pill.ts";
import * as loading from "./loading.ts";
import {page_params} from "./page_params.ts";
import * as peer_data from "./peer_data.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_pill from "./stream_pill.ts";
import * as timerender from "./timerender.ts";
import type {HTMLSelectOneElement} from "./types.ts";
import * as ui_report from "./ui_report.ts";
import * as user_group_picker_pill from "./user_group_picker_pill.ts";
import * as user_group_pill from "./user_group_pill.ts";
import * as util from "./util.ts";

let custom_expiration_time_input = 10;
let custom_expiration_time_unit = "days";
let email_pill_widget: email_pill.EmailPillWidget;
let stream_pill_widget: stream_pill.StreamPillWidget;
let user_group_pill_widget: user_group_pill.UserGroupPillWidget;
let guest_invite_stream_ids: number[] = [];

function reset_error_messages(): void {
    $("#dialog_error").hide().text("").removeClass(common.status_classes);

    if (page_params.development_environment) {
        $("#dev_env_msg").hide().text("").removeClass(common.status_classes);
    }
}

function get_common_invitation_data(): {
    csrfmiddlewaretoken: string;
    invite_as: number;
    notify_referrer_on_join: boolean;
    stream_ids: string;
    invite_expires_in_minutes: string;
    invitee_emails: string;
    include_realm_default_subscriptions: string;
} {
    const invite_as = Number.parseInt(
        $<HTMLSelectOneElement>("select:not([multiple])#invite_as").val()!,
        10,
    );
    const notify_referrer_on_join = $("#receive-invite-acceptance-notification").is(":checked");
    const raw_expires_in = $<HTMLSelectOneElement>("select:not([multiple])#expires_in").val()!;
    // See settings_config.expires_in_values for why we do this conversion.
    let expires_in: number | null;
    if (raw_expires_in === "null") {
        expires_in = null;
    } else if (raw_expires_in === "custom") {
        expires_in = util.get_custom_time_in_minutes(
            custom_expiration_time_unit,
            custom_expiration_time_input,
        );
    } else {
        expires_in = Number.parseFloat(raw_expires_in);
    }

    let stream_ids: number[] = [];
    let include_realm_default_subscriptions = false;
    if ($("#invite_select_default_streams").prop("checked")) {
        include_realm_default_subscriptions = true;
    } else {
        stream_ids = stream_pill.get_stream_ids(stream_pill_widget);
    }
    let group_ids: number[] = [];
    if (user_group_pill_widget !== undefined) {
        group_ids = user_group_pill.get_group_ids(user_group_pill_widget);
    }

    assert(csrf_token !== undefined);
    const data = {
        csrfmiddlewaretoken: csrf_token,
        invite_as,
        notify_referrer_on_join,
        stream_ids: JSON.stringify(stream_ids),
        invite_expires_in_minutes: JSON.stringify(expires_in),
        group_ids: JSON.stringify(group_ids),
        invitee_emails: email_pill_widget
            .items()
            .map((item) => item.email)
            .join(","),
        include_realm_default_subscriptions: JSON.stringify(include_realm_default_subscriptions),
    };
    const current_email = email_pill.get_current_email(email_pill_widget);
    if (current_email) {
        if (email_pill_widget.items().length === 0) {
            data.invitee_emails = current_email;
        } else {
            data.invitee_emails += "," + current_email;
        }
    }
    return data;
}

function beforeSend(): void {
    reset_error_messages();
    // TODO: You could alternatively parse the emails here, and return errors to
    // the user if they don't match certain constraints (i.e. not real email addresses,
    // aren't in the right domain, etc.)
    //
    // OR, you could just let the server do it. Probably my temptation.
    const loading_text = $("#invite-user-modal .dialog_submit_button").attr("data-loading-text");
    assert(loading_text !== undefined);
    $("#invite-user-modal .dialog_submit_button").text(loading_text);
    $("#invite-user-modal .dialog_submit_button").prop("disabled", true);
}

function submit_invitation_form(): void {
    const $expires_in = $<HTMLSelectOneElement>("select:not([multiple])#expires_in");
    const $invite_status = $("#dialog_error");
    const data = get_common_invitation_data();

    void channel.post({
        url: "/json/invites",
        data,
        beforeSend,
        success() {
            const number_of_invites_sent = email_pill_widget.items().length;
            ui_report.success(
                $t_html(
                    {
                        defaultMessage:
                            "{N, plural, one {User invited successfully.} other {Users invited successfully.}}",
                    },
                    {N: number_of_invites_sent},
                ),
                $invite_status,
            );
            email_pill_widget.clear();

            if (page_params.development_environment) {
                const rendered_email_msg = render_settings_dev_env_email_access();
                $("#dev_env_msg").html(rendered_email_msg).addClass("alert-info").show();
            }

            if ($expires_in.val() === "custom") {
                // Hide the custom inputs if the custom input is set
                // to one of the dropdown's standard options.
                const time_in_minutes = util.get_custom_time_in_minutes(
                    custom_expiration_time_unit,
                    custom_expiration_time_input,
                );
                for (const option of Object.values(settings_config.expires_in_values)) {
                    if (option.value === time_in_minutes) {
                        $("#custom-invite-expiration-time").hide();
                        $expires_in.val(time_in_minutes);
                        return;
                    }
                }
            }
        },
        error(xhr) {
            const parsed = z
                .object({
                    result: z.literal("error"),
                    code: z.literal("INVITATION_FAILED"),
                    msg: z.string(),
                    errors: z.array(z.tuple([z.string(), z.string(), z.boolean()])),
                    sent_invitations: z.boolean(),
                    license_limit_reached: z.boolean(),
                    daily_limit_reached: z.boolean(),
                })
                .safeParse(xhr.responseJSON);
            if (!parsed.success) {
                // There was a fatal error, no partial processing occurred.
                ui_report.error("", xhr, $invite_status);
            } else {
                // Some users were not invited.
                const invitee_emails_errored = [];
                const error_list = [];
                let is_invitee_deactivated = false;
                for (const [email, error_message, deactivated] of parsed.data.errors) {
                    error_list.push(`${email}: ${error_message}`);
                    if (deactivated) {
                        is_invitee_deactivated = true;
                    }
                    invitee_emails_errored.push(email);
                }

                const error_response = render_invitation_failed_error({
                    error_message: parsed.data.msg,
                    error_list,
                    is_admin: current_user.is_admin,
                    is_invitee_deactivated,
                    license_limit_reached: parsed.data.license_limit_reached,
                    has_billing_access: settings_data.user_has_billing_access(),
                    daily_limit_reached: parsed.data.daily_limit_reached,
                });
                ui_report.message(error_response, $invite_status, "alert-error");

                if (parsed.data.sent_invitations) {
                    for (const email of invitee_emails_errored) {
                        email_pill_widget.appendValue(email);
                    }
                }
            }
        },
        complete() {
            $("#invite-user-modal .dialog_submit_button").text($t({defaultMessage: "Invite"}));
            $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            $("#invite-user-modal .dialog_exit_button").prop("disabled", false);
            util.the($invite_status).scrollIntoView();
        },
    });
}

function generate_multiuse_invite(): void {
    const $invite_status = $("#dialog_error");
    const data = get_common_invitation_data();
    void channel.post({
        url: "/json/invites/multiuse",
        data,
        beforeSend,
        success(data) {
            const copy_link_html = render_copy_invite_link(data);
            ui_report.success(copy_link_html, $invite_status);
            const clipboard = new ClipboardJS("#copy_generated_invite_link");

            clipboard.on("success", () => {
                const tippy_timeout_in_ms = 800;
                show_copied_confirmation(util.the($("#copy_generated_invite_link")), {
                    show_check_icon: true,
                    timeout_in_ms: tippy_timeout_in_ms,
                });
            });
        },
        error(xhr) {
            ui_report.error("", xhr, $invite_status);
        },
        complete() {
            $("#invite-user-modal .dialog_submit_button").text($t({defaultMessage: "Create link"}));
            $("#invite-user-modal .dialog_submit_button").prop("disabled", false);
            $("#invite-user-modal .dialog_exit_button").prop("disabled", false);
            util.the($invite_status).scrollIntoView();
        },
    });
}

function valid_to(): string {
    const $expires_in = $<HTMLSelectOneElement>("select:not([multiple])#expires_in");
    const time_input_value = $expires_in.val()!;

    if (time_input_value === "null") {
        return $t({defaultMessage: "Never expires"});
    }

    let time_in_minutes: number;
    if (time_input_value === "custom") {
        if (!util.validate_custom_time_input(custom_expiration_time_input, false)) {
            return $t({defaultMessage: "Invalid custom time"});
        }
        time_in_minutes = util.get_custom_time_in_minutes(
            custom_expiration_time_unit,
            custom_expiration_time_input,
        );
    } else {
        time_in_minutes = Number.parseFloat(time_input_value);
    }

    // The below is a duplicate of timerender.get_full_datetime, with a different base string.
    const valid_to = add(new Date(), {minutes: time_in_minutes});
    const date = timerender.get_localized_date_or_time_for_format(valid_to, "dayofyear_year");
    const time = timerender.get_localized_date_or_time_for_format(valid_to, "time");

    return $t({defaultMessage: "Expires on {date} at {time}"}, {date, time});
}

function set_streams_to_join_list_visibility(): void {
    const realm_has_default_streams = stream_data.get_default_stream_ids().length > 0;
    const hide_streams_list =
        realm_has_default_streams &&
        util.the($<HTMLInputElement>("input#invite_select_default_streams")).checked;
    if (hide_streams_list) {
        $(".add_streams_container").hide();
    } else {
        $(".add_streams_container").show();
    }
}

async function update_guest_visible_users_count_and_stream_ids(): Promise<void> {
    const invite_as = Number.parseInt(
        $<HTMLSelectOneElement>("select:not([multiple])#invite_as").val()!,
        10,
    );

    assert(!Number.isNaN(invite_as));

    const guest_role_selected = invite_as === settings_config.user_role_values.guest.code;
    if (guest_role_selected) {
        guest_invite_stream_ids = stream_pill.get_stream_ids(stream_pill_widget);
    }
    if (!guest_role_selected || settings_data.guests_can_access_all_other_users()) {
        $("#guest_visible_users_container").hide();
        return;
    }
    const stream_ids = $("#invite_select_default_streams").is(":checked")
        ? stream_data.get_default_stream_ids()
        : stream_pill.get_stream_ids(stream_pill_widget);

    $(".guest-visible-users-count").empty();
    loading.make_indicator($(".guest_visible_users_loading"));
    $("#guest_visible_users_container").show();

    const visible_users_count = await peer_data.get_unique_subscriber_count_for_streams(stream_ids);
    $(".guest-visible-users-count").text(visible_users_count);
    loading.destroy_indicator($(".guest_visible_users_loading"));
}

function generate_invite_tips_data(): Record<string, boolean> {
    const {realm_description, realm_icon_source, custom_profile_fields} = realm;

    return {
        realm_has_description:
            realm_description !== "" &&
            !/^Organization imported from [A-Za-z]+[!.]$/.test(realm_description),
        realm_has_user_set_icon: realm_icon_source !== "G",
        realm_has_custom_profile_fields: custom_profile_fields.length > 0,
    };
}

function update_stream_list(): void {
    const invite_as = Number.parseInt(
        $<HTMLSelectOneElement>("select:not([multiple])#invite_as").val()!,
        10,
    );

    assert(!Number.isNaN(invite_as));

    const guest_role_selected = invite_as === settings_config.user_role_values.guest.code;
    stream_pill_widget.clear();

    if (guest_role_selected) {
        $("#invite_select_default_streams").prop("checked", false);
        $(".add_streams_container").show();
        for (const stream_id of guest_invite_stream_ids) {
            const sub = stream_data.get_sub_by_id(stream_id);
            if (sub) {
                stream_pill.append_stream(sub, stream_pill_widget, false);
            }
        }
    } else {
        $("#invite_select_default_streams").prop("checked", true);
        invite_stream_picker_pill.add_default_stream_pills(stream_pill_widget);
        set_streams_to_join_list_visibility();
    }
}

function open_invite_user_modal(e: JQuery.ClickEvent<Document, undefined>): void {
    e.stopPropagation();
    e.preventDefault();

    const show_group_pill_container =
        user_group_picker_pill.get_user_groups_allowed_to_add_members().length > 0;

    const html_body = render_invite_user_modal({
        is_admin: current_user.is_admin,
        is_owner: current_user.is_owner,
        show_group_pill_container,
        development_environment: page_params.development_environment,
        invite_as_options: settings_config.user_role_values,
        expires_in_options: settings_config.expires_in_values,
        time_choices: settings_config.custom_time_unit_values,
        show_select_default_streams_option: stream_data.get_default_stream_ids().length > 0,
        user_has_email_set: !settings_data.user_email_not_configured(),
    });

    function invite_user_modal_post_render(): void {
        const $expires_in = $<HTMLSelectOneElement>("select:not([multiple])#expires_in");
        const $pill_container = $("#invitee_emails_container .pill-container");
        email_pill_widget = email_pill.create_pills($pill_container);

        $("#invite-user-modal .dialog_submit_button").prop("disabled", true);

        const user_has_email_set = !settings_data.user_email_not_configured();

        settings_components.set_custom_time_inputs_visibility(
            $expires_in,
            custom_expiration_time_unit,
            custom_expiration_time_input,
        );
        const valid_to_text = valid_to();
        settings_components.set_time_input_formatted_text($expires_in, valid_to_text);

        set_streams_to_join_list_visibility();
        const $stream_pill_container = $("#invite_streams_container .pill-container");
        stream_pill_widget = invite_stream_picker_pill.create($stream_pill_container);

        if (show_group_pill_container) {
            const $user_group_pill_container = $("#invite-user-group-container .pill-container");
            user_group_pill_widget = user_group_picker_pill.create($user_group_pill_container);
        }

        $("#invite_streams_container .input, #invite_select_default_streams").on(
            "change",
            () => void update_guest_visible_users_count_and_stream_ids(),
        );

        $("#invite_as").on("change", () => {
            update_stream_list();
            void update_guest_visible_users_count_and_stream_ids();
        });

        $("#invite-user-modal").on("click", ".setup-tips-container .banner_content a", () => {
            dialog_widget.close();
        });

        $("#invite-user-modal").on("click", ".main-view-banner-close-button", (e) => {
            e.preventDefault();
            $(e.target).parent().remove();
        });

        function toggle_invite_submit_button(
            selected_tab: string | undefined = $(".invite_users_option_tabs")
                .find(".selected")
                .attr("data-tab-key"),
        ): void {
            const valid_custom_time = util.validate_custom_time_input(
                custom_expiration_time_input,
                false,
            );
            const $button = $("#invite-user-modal .dialog_submit_button");
            $button.prop(
                "disabled",
                !user_has_email_set ||
                    (selected_tab === "invite-email-tab" &&
                        email_pill_widget.items().length === 0 &&
                        email_pill.get_current_email(email_pill_widget) === null) ||
                    ($expires_in.val() === "custom" && !valid_custom_time),
            );
            if (selected_tab === "invite-email-tab") {
                $button.text($t({defaultMessage: "Invite"}));
                $button.attr("data-loading-text", $t({defaultMessage: "Inviting…"}));
            } else {
                $button.text($t({defaultMessage: "Create link"}));
                $button.attr("data-loading-text", $t({defaultMessage: "Creating link…"}));
            }
        }

        email_pill_widget.onPillCreate(toggle_invite_submit_button);
        email_pill_widget.onPillRemove(() => {
            toggle_invite_submit_button();
        });
        email_pill_widget.onTextInputHook(toggle_invite_submit_button);

        $expires_in.on("change", () => {
            if (!util.validate_custom_time_input(custom_expiration_time_input, false)) {
                custom_expiration_time_input = 0;
            }
            settings_components.set_custom_time_inputs_visibility(
                $expires_in,
                custom_expiration_time_unit,
                custom_expiration_time_input,
            );
            const valid_to_text = valid_to();
            settings_components.set_time_input_formatted_text($expires_in, valid_to_text);
            toggle_invite_submit_button();
        });

        $("#custom-expiration-time-input").on("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                return;
            }
        });

        $("#custom-expiration-time-input, #custom-expiration-time-unit").on("change", () => {
            custom_expiration_time_input = util.check_time_input(
                $<HTMLInputElement>("input#custom-expiration-time-input").val()!,
            );
            custom_expiration_time_unit = $<HTMLSelectOneElement>(
                "select:not([multiple])#custom-expiration-time-unit",
            ).val()!;
            const valid_to_text = valid_to();
            settings_components.set_time_input_formatted_text($expires_in, valid_to_text);
            toggle_invite_submit_button();
        });

        $("#invite_check_all_button").on("click", () => {
            $("#invite-stream-checkboxes input[type=checkbox]").prop("checked", true);
        });

        $("#invite_uncheck_all_button").on("click", () => {
            $("#invite-stream-checkboxes input[type=checkbox]").prop("checked", false);
        });

        $("#invite_select_default_streams").on("change", () => {
            set_streams_to_join_list_visibility();
        });

        if (!user_has_email_set) {
            $(util.the($<HTMLFormElement>("form#invite-user-form")).elements).prop(
                "disabled",
                true,
            );
            demo_organizations_ui.show_configure_email_banner();
        }

        // Render organization settings tips for non-demo organizations
        // and for users with admin privileges.
        if (
            realm.demo_organization_scheduled_deletion_date === undefined &&
            current_user.is_admin
        ) {
            const invite_tips_data = generate_invite_tips_data();
            const context = {
                banner_type: compose_banner.INFO,
                classname: "setup_tips_banner",
                ...invite_tips_data,
            };
            $("#invite-user-form .setup-tips-container").html(render_invite_tips_banner(context));
        }

        const toggler = components.toggle({
            html_class: "invite_users_option_tabs large allow-overflow",
            selected: 0,
            child_wants_focus: true,
            values: [
                {label: $t({defaultMessage: "Email invitation"}), key: "invite-email-tab"},
                {label: $t({defaultMessage: "Invitation link"}), key: "invite-link-tab"},
            ],
            callback(_name, key) {
                switch (key) {
                    case "invite-email-tab":
                        $("#invitee_emails_container").show();
                        $("#receive-invite-acceptance-notification-container").show();
                        break;
                    case "invite-link-tab":
                        $("#invitee_emails_container").hide();
                        $("#receive-invite-acceptance-notification-container").hide();
                        break;
                }
                toggle_invite_submit_button(key);
                reset_error_messages();
            },
        });
        const $container = $("#invite_users_option_tabs_container");
        if (!settings_data.user_can_invite_users_by_email()) {
            toggler.disable_tab("invite-email-tab");
            toggler.goto("invite-link-tab");
        }
        if (!settings_data.user_can_create_multiuse_invite()) {
            toggler.disable_tab("invite-link-tab");
        }
        const $elem = toggler.get();
        $container.append($elem);
        setTimeout(() => {
            $(".invite_users_option_tabs .ind-tab.selected").trigger("focus");
        }, 0);
    }

    function invite_users(): void {
        const is_generate_invite_link =
            $(".invite_users_option_tabs").find(".selected").attr("data-tab-key") ===
            "invite-link-tab";
        if (is_generate_invite_link) {
            generate_multiuse_invite();
        } else {
            submit_invitation_form();
        }
    }

    dialog_widget.launch({
        html_heading: $t_html({defaultMessage: "Invite users to organization"}),
        html_body,
        html_submit_button: $t_html({defaultMessage: "Invite"}),
        id: "invite-user-modal",
        loading_spinner: true,
        on_click: invite_users,
        post_render: invite_user_modal_post_render,
        always_visible_scrollbar: true,
    });
}

export function initialize(): void {
    $(document).on("click", ".invite-user-link", open_invite_user_modal);
}
