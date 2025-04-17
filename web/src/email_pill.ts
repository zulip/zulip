import {parseAddressList, parseOneAddress} from "email-addresses";

import type {InputPillConfig, InputPillContainer} from "./input_pill.ts";
import * as input_pill from "./input_pill.ts";

type EmailPill = {
    type: "email";
    email: string;
    parsed_email: string;
};

export type EmailPillWidget = InputPillContainer<EmailPill>;

export function create_item_from_email(
    email: string,
    current_items: EmailPill[],
): EmailPill | undefined {
    const original_email = email;
    const parsed_address = parseOneAddress(email);
    if (!parsed_address || parsed_address.type !== "mailbox") {
        return undefined;
    }

    const parsed_email = parsed_address.address;

    const existing_emails = current_items.map((item) => item.parsed_email);
    if (existing_emails.includes(parsed_email)) {
        return undefined;
    }

    return {
        type: "email",
        email: original_email,
        parsed_email,
    };
}

export function get_email_from_item(item: EmailPill): string {
    return item.email;
}

export function get_current_email(
    pill_container: input_pill.InputPillContainer<EmailPill>,
): string | null {
    const current_text = pill_container.getCurrentText();
    if (current_text !== null && parseOneAddress(current_text)) {
        return current_text;
    }
    return null;
}

export function split_text_to_form_email_pills(raw_emails: string): string[] {
    const parsed_emails = parseAddressList(raw_emails);
    if (!parsed_emails) {
        return [];
    }

    return parsed_emails
        .filter((email) => email.type === "mailbox")
        .map((email) => (email.name ? `"${email.name}" <${email.address}>` : email.address));
}

export function create_pills(
    $pill_container: JQuery,
    pill_config?: InputPillConfig,
): input_pill.InputPillContainer<EmailPill> {
    const pill_container = input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_email,
        get_text_from_item: get_email_from_item,
        get_display_value_from_item: get_email_from_item,
        split_text_on_comma: false,
        split_text_to_form_pills: split_text_to_form_email_pills,
    });
    return pill_container;
}
