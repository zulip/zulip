import $ from "jquery";

import * as loading from "../loading";
import {page_params} from "../page_params";



export function create_ajax_request(
    url:string,
    form_name:string,
    ignored_inputs:string[],
    type = "POST",
    success_callback: (response: any) => void,
) {
    const $form = $(`#${CSS.escape(form_name)}-form`);
    const form_loading_indicator = `#${CSS.escape(form_name)}_loading_indicator`;
    const form_input_section = `#${CSS.escape(form_name)}-input-section`;
    const form_success = `#${CSS.escape(form_name)}-success`;
    const form_error = `#${CSS.escape(form_name)}-error`;
    const form_loading = `#${CSS.escape(form_name)}-loading`;

    const zulip_limited_section:string = "#zulip-limited-section";
    const free_trial_alert_message:string = "#free-trial-alert-message";

    loading.make_indicator($(form_loading_indicator), {
        text: "Processing ...",
        abs_positioned: true,
    });
    $(form_input_section).hide();
    $(form_error).hide();
    $(form_loading).show();
    $(zulip_limited_section).hide();
    $(free_trial_alert_message).hide();

    type data =  { [key: string]: string;}
    const data: data = {};

    for (const item of $form.serializeArray()) {
        if (ignored_inputs.includes(item.name)) {
            continue;
        }
        data[item.name] = item.value;
    }

    $.ajax({
        type,
        url,
        data,
        success(response:object) {
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
        error(xhr:XMLHttpRequest) {
            $(form_loading).hide();
            $(form_error).show().text(JSON.parse(xhr.responseText).msg);
            $(form_input_section).show();
            $(zulip_limited_section).show();
            $(free_trial_alert_message).show();
        },
    });
}

export function format_money(cents: number) {
    // allow for small floating point errors
    cents = Math.ceil(cents - 0.001);
    let precision;
    if (cents % 100 === 0) {
        precision = 0;
    } else {
        precision = 2;
    }
    // TODO: Add commas for thousands, millions, etc.
    return (cents / 100).toFixed(precision);
}

export function update_charged_amount(prices: { [x: string]: number; }, schedule: string | number) {
    $("#charged_amount").text(format_money(page_params.seat_count * prices[schedule]));
}
interface DiscountDetails {
    opensource: string;
    research: string;
    nonprofit: string;
    event: string;
    education: string;
    education_nonprofit: string;

}
export function update_discount_details(organization_type: string | number) {
    let discount_notice =
        "Your organization may be eligible for a discount on Zulip Cloud Standard. Organizations whose members are not employees are generally eligible.";
    const discount_details = {
        opensource: "Zulip Cloud Standard is free for open-source projects.",
        research: "Zulip Cloud Standard is free for academic research.",
        nonprofit: "Zulip Cloud Standard is discounted 85%+ for registered non-profits.",
        event: "Zulip Cloud Standard is free for academic conferences and most non-profit events.",
        education: "Zulip Cloud Standard is discounted 85% for education.",
        education_nonprofit:
            "Zulip Cloud Standard is discounted 90% for education non-profits with online purchase.",
    };
    if (discount_details[organization_type as keyof DiscountDetails]) {
        discount_notice = discount_details[organization_type as keyof DiscountDetails];
    }
    $("#sponsorship-discount-details").text(discount_notice);
}

export function show_license_section(license: string) {
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

function handle_hashchange() {
    $(`#${CSS.escape(current_page)}-tabs.nav a[href="${CSS.escape(location.hash)}"]`).tab("show");
    $("html").scrollTop(0);
}

export function set_tab(page: string) {
    const hash = location.hash;
    if (hash) {
        $(`#${CSS.escape(page)}-tabs.nav a[href="${CSS.escape(hash)}"]`).tab("show");
        $("html").scrollTop(0);
    }

    $(`#${CSS.escape(page )}-tabs.nav-tabs a`).on("click", function (this:any) {
        location.hash = this.hash;
    });

    current_page = page;
    window.addEventListener("hashchange", handle_hashchange);
}

export function is_valid_input(elem: { checkValidity: () => any; }[]) {
    return elem[0].checkValidity();
}
