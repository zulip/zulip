import $ from "jquery";
import {z} from "zod";

import * as loading from "../loading";

export type FormDataObject = Record<string, string>;

export const schedule_schema = z.enum(["monthly", "annual"]);
export type Prices = Record<z.infer<typeof schedule_schema>, number>;

export const organization_type_schema = z.enum([
    "opensource",
    "research",
    "nonprofit",
    "event",
    "education",
    "education_nonprofit",
]);
export type DiscountDetails = Record<z.infer<typeof organization_type_schema>, string>;

export const stripe_session_url_schema = z.object({
    stripe_session_url: z.string(),
});

const cloud_discount_details: DiscountDetails = {
    opensource: "Zulip Cloud Standard is free for open-source projects.",
    research: "Zulip Cloud Standard is free for academic research.",
    nonprofit: "Zulip Cloud Standard is discounted 85%+ for registered non-profits.",
    event: "Zulip Cloud Standard is free for academic conferences and most non-profit events.",
    education: "Zulip Cloud Standard is discounted 85% for education.",
    education_nonprofit:
        "Zulip Cloud Standard is discounted 90% for education non-profits with online purchase.",
};

const remote_discount_details: DiscountDetails = {
    opensource: "The Community plan is free for open-source projects.",
    research: "The Community plan is free for academic research.",
    nonprofit:
        "The Community plan is free for registered non-profits with up to 100 users. For larger organizations, paid plans are discounted by 85+%.",
    event: "The Community plan is free for academic conferences and most non-profit events.",
    education:
        "The Community plan is free for education organizations with up to 100 users. For larger organizations, paid plans are discounted by 85%.",
    education_nonprofit:
        "The Community plan is free for education non-profits with up to 100 users. For larger organizations, paid plans are discounted by 90% with online purchase.",
};

export function create_ajax_request(
    url: string,
    form_name: string,
    ignored_inputs: string[] = [],
    type = "POST",
    success_callback: (response: unknown) => void,
    error_callback: (xhr: JQuery.jqXHR) => void = () => {
        // Ignore errors by default
    },
): void {
    const $form = $(`#${CSS.escape(form_name)}-form`);
    const form_loading_indicator = `#${CSS.escape(form_name)}_loading_indicator`;
    const form_input_section = `#${CSS.escape(form_name)}-input-section`;
    const form_success = `#${CSS.escape(form_name)}-success`;
    const form_error = `#${CSS.escape(form_name)}-error`;
    const form_loading = `#${CSS.escape(form_name)}-loading`;

    loading.make_indicator($(form_loading_indicator), {
        text: "Processing ...",
        abs_positioned: true,
    });
    $(form_input_section).hide();
    $(form_error).hide();
    $(form_loading).show();

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
            const parsed = z.object({msg: z.string()}).safeParse(xhr.responseJSON);
            if (parsed.success) {
                $(form_error).show().text(parsed.data.msg);
            }
            $(form_input_section).show();
            error_callback(xhr);

            if (xhr.status === 401) {
                // User session timed out, we need to login again.
                const parsed = z.object({login_url: z.string()}).safeParse(xhr.responseJSON);
                if (parsed.success) {
                    window.location.href = parsed.data.login_url;
                }
            }
        },
    });
}

// This function imitates the behavior of the format_money in views/billing_page.py
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

export function update_discount_details(
    organization_type: string,
    is_remotely_hosted: boolean,
): void {
    let discount_notice = is_remotely_hosted
        ? "Your organization may be eligible for a free Community plan, or a discounted Business plan."
        : "Your organization may be eligible for a discount on Zulip Cloud Standard. Organizations whose members are not employees are generally eligible.";

    try {
        const parsed_organization_type = organization_type_schema.parse(organization_type);
        discount_notice = is_remotely_hosted
            ? remote_discount_details[parsed_organization_type]
            : cloud_discount_details[parsed_organization_type];
    } catch {
        // This will likely fail if organization_type is not in organization_type_schema or
        // parsed_organization_type is not preset in discount_details. In either case, we will
        // fallback to the default discount_notice.
        //
        // Why use try / catch?
        // Because organization_type_schema.options.includes wants organization_type to be of type
        // opensource | research | ... and defining a type like that is not useful.
    }

    $("#sponsorship-discount-details").text(discount_notice);
}

export function is_valid_input(elem: JQuery<HTMLFormElement>): boolean {
    return elem[0].checkValidity();
}

export function redirect_to_billing_with_successful_upgrade(billing_base_url: string): void {
    window.location.replace(
        billing_base_url +
            "/billing/?success_message=" +
            encodeURIComponent("Your organization has been upgraded to PLAN_NAME."),
    );
}

export function get_upgrade_page_url(
    is_manual_license_management_upgrade_session: boolean | undefined,
    tier: number,
    billing_base_url: string,
): string {
    const base_url = billing_base_url + "/upgrade/";
    let params = `tier=${String(tier)}`;
    if (is_manual_license_management_upgrade_session !== undefined) {
        params += `&manual_license_management=${String(
            is_manual_license_management_upgrade_session,
        )}`;
    }
    return base_url + "?" + params;
}
