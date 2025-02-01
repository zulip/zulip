import {parseOneAddress} from "email-addresses";

import type {InputPillConfig, InputPillContainer} from "./input_pill.ts";
import * as input_pill from "./input_pill.ts";
import type {Invitees} from "./invite.ts";

type EmailPill = {
    type: "email";
    original_email: string;
    email: string;
    full_name: string;
};

export type EmailPillWidget = InputPillContainer<EmailPill>;

export function create_item_from_email(
    email: string,
    current_items: EmailPill[],
): EmailPill | undefined {
    const original_email = email;
    const extracted_email = parseOneAddress(original_email);
    let full_name = "";

    if (extracted_email) {
        if (extracted_email.type === "mailbox") {
            email = extracted_email.address;
            full_name = extracted_email.name ?? "";
        } else {
            return undefined;
        }

        const existing_emails = current_items.map((item) => item.email);
        if (existing_emails.includes(email)) {
            return undefined;
        }

        return {
            type: "email",
            original_email,
            email,
            full_name,
        };
    }
    return undefined;
}

export function get_text_from_item(item: EmailPill): string {
    return item.original_email;
}

export function get_invitee_from_item(item: EmailPill): Invitees {
    return {
        email: item.email,
        full_name: item.full_name,
    };
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

export function create_pills(
    $pill_container: JQuery,
    pill_config?: InputPillConfig,
): input_pill.InputPillContainer<EmailPill> {
    const pill_container = input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_email,
        get_text_from_item,
        get_display_value_from_item: get_text_from_item,
        split_text_on_comma: false,
    });
    return pill_container;
}
