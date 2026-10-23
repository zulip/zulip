import type {InputPillConfig, InputPillContainer} from "./input_pill.ts";
import * as input_pill from "./input_pill.ts";

type CustomFieldPill = {
    type: "custom_field";
    value: string;
};

export type CustomFieldPillWidget = InputPillContainer<CustomFieldPill>;

export function create_item_from_custom_field_name(
    value: string,
    current_items: CustomFieldPill[],
): CustomFieldPill | undefined {
    const trimmed_value = value.trim();
    const normalized_value = trimmed_value.toLowerCase();
    const existing_fields = current_items.map((item) => item.value.toLowerCase());
    if (trimmed_value === "" || existing_fields.includes(normalized_value)) {
        return undefined;
    }
    return {
        type: "custom_field",
        value: trimmed_value,
    };
}

export function get_custom_field_name_from_item(item: CustomFieldPill): string {
    return item.value;
}

export function create_pills(
    $pill_container: JQuery,
    pill_config?: InputPillConfig,
): CustomFieldPillWidget {
    return input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_custom_field_name,
        get_text_from_item: get_custom_field_name_from_item,
        get_display_value_from_item: get_custom_field_name_from_item,
    });
}

export function add_default_custom_fields(
    custom_field_pill_widget: CustomFieldPillWidget,
    default_custom_fields: string[],
): void {
    for (const field_name of default_custom_fields) {
        custom_field_pill_widget.appendValidatedData(
            {
                type: "custom_field",
                value: field_name,
            },
            true,
            true,
        );
    }
}

export function get_additional_custom_fields(
    custom_field_pill_widget: CustomFieldPillWidget,
    default_custom_fields: string[],
): string {
    return custom_field_pill_widget
        .items()
        .map((item) => item.value)
        .filter((value) => !default_custom_fields.includes(value.toLowerCase()))
        .join(",");
}
