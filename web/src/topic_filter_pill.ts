import render_input_pill from "../templates/input_pill.hbs";

import {$t} from "./i18n.ts";
import type {InputPillConfig, InputPillContainer} from "./input_pill.ts";
import * as input_pill from "./input_pill.ts";

export type TopicFilterPill = {
    type: "topic_filter";
    label: string;
    syntax: string;
};

export type TopicFilterPillWidget = InputPillContainer<TopicFilterPill>;

export const filter_options: TopicFilterPill[] = [
    {
        type: "topic_filter",
        label: $t({defaultMessage: "unresolved"}),
        syntax: "-is:resolved",
    },
    {
        type: "topic_filter",
        label: $t({defaultMessage: "resolved"}),
        syntax: "is:resolved",
    },
];

export function create_item_from_syntax(
    syntax: string,
    current_items: TopicFilterPill[],
): TopicFilterPill | undefined {
    const existing_syntaxes = current_items.map((item) => item.syntax);
    if (existing_syntaxes.includes(syntax)) {
        return undefined;
    }

    // Find the matching filter option
    const filter_option = filter_options.find((option) => option.syntax === syntax);
    if (!filter_option) {
        return undefined;
    }
    return filter_option;
}

export function get_syntax_from_item(item: TopicFilterPill): string {
    return item.syntax;
}

export function create_pills(
    $pill_container: JQuery,
    pill_config?: InputPillConfig,
): TopicFilterPillWidget {
    const pill_container = input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_syntax,
        get_text_from_item: get_syntax_from_item,
        get_display_value_from_item: get_syntax_from_item,
        generate_pill_html(item: TopicFilterPill, disabled?: boolean) {
            return render_input_pill({
                display_value: item.label,
                disabled,
            });
        },
    });
    pill_container.createPillonPaste(() => false);
    return pill_container;
}
