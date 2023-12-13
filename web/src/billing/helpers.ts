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

export function create_ajax_request(
    url: string,
    form_name: string,
    ignored_inputs: string[] = [],
    type = "POST",
    success_callback: (response: unknown) => void,
    error_callback: (xhr: JQuery.jqXHR) => void = () => {},
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
            if (xhr.responseJSON?.msg) {
                $(form_error).show().text(xhr.responseJSON.msg);
            }
            $(form_input_section).show();
            error_callback(xhr);
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

export function update_discount_details(organization_type: string): void {
    const plan_name_element = document.querySelector("#sponsorship-plan-name-hidden-info");
    const plan_name = plan_name_element?.getAttribute("data-plan-name") || "Zulip Cloud Standard";

    let discount_notice = `Your organization may be eligible for a discount on the ${plan_name} plan. Organizations whose members are not employees are generally eligible.`;
    const discount_details: DiscountDetails = {
        opensource: `${plan_name} plan is free for open-source projects.`,
        research: `${plan_name} plan is free for academic research.`,
        nonprofit: `${plan_name} plan is discounted 85%+ for registered non-profits.`,
        event: `${plan_name} plan is free for academic conferences and most non-profit events.`,
        education: `${plan_name} plan is discounted 85% for education.`,
        education_nonprofit: `${plan_name} plan is discounted 90% for education non-profits with online purchase.`,
    };

    try {
        const parsed_organization_type = organization_type_schema.parse(organization_type);
        discount_notice = discount_details[parsed_organization_type];
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
    billing_base_url: string,
): string {
    let redirect_to = "/upgrade";
    if (is_manual_license_management_upgrade_session) {
        redirect_to += "/?manual_license_management=true";
    }
    return billing_base_url + redirect_to;
}
