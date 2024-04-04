import $ from "jquery";

import render_convert_demo_organization_form from "../templates/settings/convert_demo_organization_form.hbs";
import render_demo_organization_warning from "../templates/settings/demo_organization_warning.hbs";

import * as channel from "./channel";
import * as dialog_widget from "./dialog_widget";
import {$t} from "./i18n";
import * as keydown_util from "./keydown_util";
import {get_demo_organization_deadline_days_remaining} from "./navbar_alerts";
import * as settings_config from "./settings_config";
import * as settings_data from "./settings_data";
import * as settings_org from "./settings_org";
import {current_user, realm} from "./state_data";

export function insert_demo_organization_warning() {
    const days_remaining = get_demo_organization_deadline_days_remaining();
    const rendered_demo_organization_warning = render_demo_organization_warning({
        is_demo_organization: realm.demo_organization_scheduled_deletion_date,
        is_owner: current_user.is_owner,
        days_remaining,
    });
    $(".organization-box").find(".settings-section").prepend($(rendered_demo_organization_warning));
}

export function handle_demo_organization_conversion() {
    $(".convert-demo-organization-button").on("click", () => {
        if (!current_user.is_owner) {
            return;
        }

        const email_set = !settings_data.user_email_not_configured();
        const parts = new URL(realm.realm_uri).hostname.split(".");
        parts.shift();
        const domain = parts.join(".");
        const html_body = render_convert_demo_organization_form({
            realm_domain: domain,
            user_has_email_set: email_set,
            realm_org_type_values: settings_org.get_org_type_dropdown_options(),
        });

        function demo_organization_conversion_post_render() {
            const $convert_submit_button = $(
                "#demo-organization-conversion-modal .dialog_submit_button",
            );
            $convert_submit_button.prop("disabled", true);
            $("#add_organization_type").val(realm.realm_org_type);

            if (!email_set) {
                // Disable form fields if demo organization owner email not set.
                $("#add_organization_type").prop("disabled", true);
                $("#new_subdomain").prop("disabled", true);
            } else {
                // Disable submit button if either form field blank.
                $("#convert-demo-organization-form").on("input change", () => {
                    const string_id = $("#new_subdomain").val().trim();
                    const org_type = $("#add_organization_type").val();
                    $convert_submit_button.prop(
                        "disabled",
                        string_id === "" ||
                            Number.parseInt(org_type, 10) ===
                                settings_config.all_org_type_values.unspecified.code,
                    );
                });
            }
        }

        function submit_subdomain() {
            const $string_id = $("#new_subdomain");
            const $organization_type = $("#add_organization_type");
            const data = {
                string_id: $string_id.val(),
                org_type: $organization_type.val(),
            };
            const opts = {
                success_continuation(data) {
                    window.location.href = data.realm_uri;
                },
            };
            dialog_widget.submit_api_request(channel.patch, "/json/realm", data, opts);
        }

        dialog_widget.launch({
            html_heading: $t({defaultMessage: "Make organization permanent"}),
            html_body,
            on_click: submit_subdomain,
            post_render: demo_organization_conversion_post_render,
            html_submit_button: $t({defaultMessage: "Convert"}),
            id: "demo-organization-conversion-modal",
            loading_spinner: true,
            help_link:
                "/help/demo-organizations#convert-a-demo-organization-to-a-permanent-organization",
        });
    });

    // Treat Enter with convert demo organization link as a click.
    $(".demo-organization-warning").on(
        "keyup",
        ".convert-demo-organization-button[role=button]",
        function (e) {
            e.stopPropagation();
            if (keydown_util.is_enter_event(e)) {
                $(this).trigger("click");
            }
        },
    );
}
