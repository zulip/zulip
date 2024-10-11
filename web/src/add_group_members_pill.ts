import * as keydown_util from "./keydown_util";
import * as stream_pill from "./stream_pill";
import type {CombinedPillContainer} from "./typeahead_helper";
import * as user_group_pill from "./user_group_pill";
import * as user_pill from "./user_pill";

function get_pill_user_ids(pill_widget: CombinedPillContainer): number[] {
    const user_ids = user_pill.get_user_ids(pill_widget);
    const stream_user_ids = stream_pill.get_user_ids(pill_widget);
    return [...user_ids, ...stream_user_ids];
}

function get_pill_group_ids(pill_widget: CombinedPillContainer): number[] {
    const group_user_ids = user_group_pill.get_group_ids(pill_widget);
    return group_user_ids;
}

export function set_up_handlers({
    get_pill_widget,
    $parent_container,
    pill_selector,
    button_selector,
    action,
}: {
    get_pill_widget: () => CombinedPillContainer;
    $parent_container: JQuery;
    pill_selector: string;
    button_selector: string;
    action: ({
        pill_user_ids,
        pill_group_ids,
    }: {
        pill_user_ids: number[];
        pill_group_ids: number[];
    }) => void;
}): void {
    /*
        This is similar to add_subscribers_pill.set_up_handlers
        with only difference that selecting a user group does
        not add all its members to list, but instead just adds
        the group itself.
    */
    function callback(): void {
        const pill_widget = get_pill_widget();
        const pill_user_ids = get_pill_user_ids(pill_widget);
        const pill_group_ids = get_pill_group_ids(pill_widget);
        action({pill_user_ids, pill_group_ids});
    }

    $parent_container.on("keyup", pill_selector, (e) => {
        if (keydown_util.is_enter_event(e)) {
            e.preventDefault();
            callback();
        }
    });

    $parent_container.on("click", button_selector, (e) => {
        e.preventDefault();
        callback();
    });
}
