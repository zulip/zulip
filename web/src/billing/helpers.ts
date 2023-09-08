import $ from "jquery";
import {z} from "zod";

import * as loading from "../loading";

import {page_params} from "./page_params";

type FormDataObject = Record<string, string>;

export type Prices = {
    monthly: number;
    annual: number;
};

export type DiscountDetails = {
    opensource: string;
    research: string;
    nonprofit: string;
    event: string;
    education: string;
    education_nonprofit: string;
};

export const stripe_session_url_schema = z.object({
    stripe_session_url: z.string(),
});

export function create_ajax_request(
    url: string,
    form_name: string,
    ignored_inputs: string[] = [],
    type = "POST",
    success_callback: (response: unknown) => void,
): void {
    const $form = $(`#${CSS.escape(form_name)}-form`);
    const form_loading_indicator = `#${CSS.escape(form_name)}_loading_indicator`;
    const form_input_section = `#${CSS.escape(form_name)}-input-section`;
    const form_success = `#${CSS.escape(form_name)}-success`;
    const form_error = `#${CSS.escape(form_name)}-error`;
    const form_loading = `#${CSS.escape(form_name)}-loading`;

    const zulip_limited_section = "#zulip-limited-section";
    const free_trial_alert_message = "#free-trial-alert-message";

    loading.make_indicator($(form_loading_indicator), {
        text: "Processing ...",
        abs_positioned: true,
    });
    $(form_input_section).hide();
    $(form_error).hide();
    $(form_loading).show();
    $(zulip_limited_section).hide();
    $(free_trial_alert_message).hide();

    const data: FormDataObject = {};

    for (const item of $form.serializeArray()) {
        if (ignored_inputs.includes(item.name)) {
            continue;
        }
        data[item.name] = item.value;
    }

    void $.ajax({
        type,
        url,
        data,
        success(response: unknown) {
            $(form_loading).hide();
            $(form_error).hide();
            $(form_success).show();
            if (["autopay", "invoice"].includes(form_name)) {
                if ("pushState" in history) {
                    history.pushState("", document.title, location.pathname + location.search);
                } else {
                    location.hash = "";
                }
            }
            success_callback(response);
        },
        error(xhr) {
            $(form_loading).hide();
            if (xhr.responseJSON?.msg) {
                $(form_error).show().text(xhr.responseJSON.msg);
            }
            $(form_input_section).show();
            $(zulip_limited_section).show();
            $(free_trial_alert_message).show();
        },
    });
}

export function format_money(cents: number): string {
    // allow for small floating point errors
    cents = Math.ceil(cents - 0.001);
    let precision;
    if (cents % 100 === 0) {
        precision = 0;
    } else {
        precision = 2;
    }
    return new Intl.NumberFormat("en-US", {
        minimumFractionDigits: precision,
        maximumFractionDigits: precision,
    }).format(Number.parseFloat((cents / 100).toFixed(precision)));
}

export function update_charged_amount(prices: Prices, schedule: keyof Prices): void {
    $("#charged_amount").text(format_money(page_params.seat_count * prices[schedule]));
}

export function update_discount_details(organization_type: keyof DiscountDetails): void {
    let discount_notice =
        "Your organization may be eligible for a discount on Zulip Cloud Standard. Organizations whose members are not employees are generally eligible.";
    const discount_details: DiscountDetails = {
        opensource: "Zulip Cloud Standard is free for open-source projects.",
        research: "Zulip Cloud Standard is free for academic research.",
        nonprofit: "Zulip Cloud Standard is discounted 85%+ for registered non-profits.",
        event: "Zulip Cloud Standard is free for academic conferences and most non-profit events.",
        education: "Zulip Cloud Standard is discounted 85% for education.",
        education_nonprofit:
            "Zulip Cloud Standard is discounted 90% for education non-profits with online purchase.",
    };
    if (discount_details[organization_type]) {
        discount_notice = discount_details[organization_type];
    }
    $("#sponsorship-discount-details").text(discount_notice);
}

export function show_license_section(license: string): void {
    $("#license-automatic-section").hide();
    $("#license-manual-section").hide();

    $("#automatic_license_count").prop("disabled", true);
    $("#manual_license_count").prop("disabled", true);

    const section_id = `#license-${CSS.escape(license)}-section`;
    $(section_id).show();
    const input_id = `#${CSS.escape(license)}_license_count`;
    $(input_id).prop("disabled", false);
}

let current_page: string;

function handle_hashchange(): void {
    $(`#${CSS.escape(current_page)}-tabs.nav a[href="${CSS.escape(location.hash)}"]`).tab("show");
    $("html").scrollTop(0);
}

export function set_tab(page: string): void {
    const hash = location.hash;
    if (hash) {
        $(`#${CSS.escape(page)}-tabs.nav a[href="${CSS.escape(hash)}"]`).tab("show");
        $("html").scrollTop(0);
    }

    $<HTMLAnchorElement>(`#${CSS.escape(page)}-tabs.nav-tabs a`).on("click", function () {
        location.hash = this.hash;
    });

    current_page = page;
    window.addEventListener("hashchange", handle_hashchange);
}

export function set_sponsorship_form(): void {
    $("#sponsorship-button").on("click", (e) => {
        if (!is_valid_input($("#sponsorship-form"))) {
            return;
        }
        e.preventDefault();
        create_ajax_request("/json/billing/sponsorship", "sponsorship", [], "POST", () =>
            window.location.replace("/"),
        );
    });
}

export function is_valid_input(elem: JQuery<HTMLFormElement>): boolean {
    return elem[0].checkValidity();
}
