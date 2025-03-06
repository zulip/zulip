import type {InputPillConfig, InputPillContainer} from "./input_pill.ts";
import * as input_pill from "./input_pill.ts";

type BranchPill = {
    type: "branch";
    branch: string;
};

export type BranchPillWidget = InputPillContainer<BranchPill>;

export function create_item_from_branch_name(
    branch: string,
    current_items: BranchPill[],
): BranchPill | undefined {
    const existing_branches = current_items.map((item) => item.branch);
    return existing_branches.includes(branch) ? undefined : {type: "branch", branch};
}

export function get_branch_name_from_item(item: BranchPill): string {
    return item.branch;
}

export function create_pills(
    $pill_container: JQuery,
    pill_config?: InputPillConfig,
): input_pill.InputPillContainer<BranchPill> {
    const pill_container = input_pill.create({
        $container: $pill_container,
        pill_config,
        create_item_from_text: create_item_from_branch_name,
        get_text_from_item: get_branch_name_from_item,
        get_display_value_from_item: get_branch_name_from_item,
    });
    return pill_container;
}
