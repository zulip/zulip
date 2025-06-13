import $ from "jquery";
import assert from "minimalistic-assert";
import * as z from "zod/mini";

import render_convert_demo_organization_form from "../templates/settings/convert_demo_organization_form.hbs";
import render_demo_organization_warning_container from "../templates/settings/demo_organization_warning.hbs";

import * as banners from "./banners.ts";
import type {ActionButton} from "./buttons.ts";
import * as channel from "./channel.ts";
import * as dialog_widget from "./dialog_widget.ts";
import {$t} from "./i18n.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_data from "./settings_data.ts";
import * as settings_org from "./settings_org.ts";
import type {RequestOpts} from "./settings_ui.ts";
import {current_user, realm} from "./state_data.ts";
import type {HTMLSelectOneElement} from "./types.ts";

export function get_demo_organization_deadline_days_remaining(): number {
    const now = Date.now();
    assert(realm.demo_organization_scheduled_deletion_date !== undefined);
    const deadline = realm.demo_organization_scheduled_deletion_date * 1000;
    const day = 24 * 60 * 60 * 1000; // hours * minutes * seconds * milliseconds
    const days_remaining = Math.round(Math.abs(deadline - now) / day);
    return days_remaining;
}

export function insert_demo_organization_warning(): void {
    const demo_organization_warning_container = render_demo_organization_warning_container({
        is_demo_organization: true,
    });
    $(".organization-box")
        .find(".settings-section")
        .prepend($(demo_organization_warning_container));
    const days_remaining = get_demo_organization_deadline_days_remaining();
    let buttons: ActionButton[] = [
        {
            attention: "borderless",
            label: $t({defaultMessage: "Learn more"}),
            custom_classes: "demo-organizations-help",
        },
    ];
    if (current_user.is_owner) {
        buttons = [
            ...buttons,
            {
                attention: "quiet",
                label: $t({defaultMessage: "Convert"}),
                custom_classes: "convert-demo-organization",
            },
        ];
    }
    const demo_organization_warning_banner: banners.Banner = {
        intent: days_remaining <= 7 ? "danger" : "info",
        label: $t(
            {
                defaultMessage:
                    "This demo organization will be automatically deleted in {days_remaining} days, unless it's converted into a permanent organization.",
            },
            {
                days_remaining,
            },
        ),
        buttons,
        close_button: false,
        custom_classes: "organization-settings-banner",
    };
    banners.append(demo_organization_warning_banner, $(".demo-organization-warning"));
}

export function show_configure_email_banner(): void {
    const $configure_email_banner_container = $(".demo-organization-add-email-banner");
    if ($configure_email_banner_container.length > 0) {
        const CONFIGURE_EMAIL_BANNER: banners.Banner = {
            intent: "warning",
            label: $t({defaultMessage: "Add your email to access this feature."}),
            buttons: [
                {
                    attention: "primary",
                    label: $t({defaultMessage: "Add"}),
                    custom_classes: "demo-organization-add-email",
                },
            ],
            close_button: false,
        };
        banners.open(CONFIGURE_EMAIL_BANNER, $configure_email_banner_container);
    }

    $configure_email_banner_container.on("click", ".demo-organization-add-email", (e) => {
        e.preventDefault();
        window.location.href = "/#settings/account-and-privacy";
    });
}

export function show_convert_demo_organization_modal(): void {
    if (!current_user.is_owner) {
        return;
    }

    const email_set = !settings_data.user_email_not_configured();
    const parts = new URL(realm.realm_url).hostname.split(".");
    parts.shift();
    const domain = parts.join(".");
    const html_body = render_convert_demo_organization_form({
        realm_domain: domain,
        user_has_email_set: email_set,
        realm_org_type_values: settings_org.get_org_type_dropdown_options(),
    });

    function demo_organization_conversion_post_render(): void {
        const $convert_submit_button = $(
            "#demo-organization-conversion-modal .dialog_submit_button",
        );
        $convert_submit_button.prop("disabled", true);
        $("#add_organization_type").val(realm.realm_org_type);

        if (!email_set) {
            // Disable form fields if demo organization owner email not set.
            $("#add_organization_type").prop("disabled", true);
            $("#new_subdomain").prop("disabled", true);
            // Show banner for adding email to account.
            show_configure_email_banner();
        } else {
            // Disable submit button if either form field blank.
            $("#convert-demo-organization-form").on("input change", () => {
                const string_id = $<HTMLInputElement>("input#new_subdomain").val()!.trim();
                const org_type = $<HTMLSelectOneElement>(
                    "select:not([multiple])#add_organization_type",
                ).val()!;
                $convert_submit_button.prop(
                    "disabled",
                    string_id === "" ||
                        Number.parseInt(org_type, 10) ===
                            settings_config.all_org_type_values.unspecified.code,
                );
            });
        }
    }

    function submit_subdomain(): void {
        const $string_id = $("#new_subdomain");
        const $organization_type = $("#add_organization_type");
        const data = {
            string_id: $string_id.val(),
            org_type: $organization_type.val(),
        };
        const opts: RequestOpts = {
            success_continuation(raw_data) {
                const data = z.object({realm_url: z.string()}).parse(raw_data);
                window.location.href = data.realm_url;
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
}

export function handle_demo_organization_conversion(): void {
    $(".demo-organization-warning").on("click", ".convert-demo-organization", (e) => {
        e.stopPropagation();
        e.preventDefault();
        show_convert_demo_organization_modal();
    });

    $(".demo-organization-warning").on("click", ".demo-organizations-help", () => {
        window.open("https://zulip.com/help/demo-organizations", "_blank", "noopener,noreferrer");
    });
}
