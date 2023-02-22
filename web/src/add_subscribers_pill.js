import * as input_pill from "./input_pill";
import * as keydown_util from "./keydown_util";
import * as pill_typeahead from "./pill_typeahead";
import * as stream_pill from "./stream_pill";
import * as user_group_pill from "./user_group_pill";
import * as user_pill from "./user_pill";

function create_item_from_text(text, current_items) {
    const funcs = [
        stream_pill.create_item_from_stream_name,
        user_group_pill.create_item_from_group_name,
        user_pill.create_item_from_email,
    ];
    for (const func of funcs) {
        const item = func(text, current_items);
        if (item) {
            return item;
        }
    }
    return undefined;
}

function get_text_from_item(item) {
    const funcs = [
        stream_pill.get_stream_name_from_item,
        user_group_pill.get_group_name_from_item,
        user_pill.get_email_from_item,
    ];
    for (const func of funcs) {
        const text = func(item);
        if (text) {
            return text;
        }
    }
    return undefined;
}

function set_up_pill_typeahead({pill_widget, $pill_container, get_users}) {
    const opts = {
        user_source: get_users,
        stream: true,
        user_group: true,
        user: true,
    };
    pill_typeahead.set_up($pill_container.find(".input"), pill_widget, opts);
}

export function create({$pill_container, get_potential_subscribers}) {
    const pill_widget = input_pill.create({
        $container: $pill_container,
        create_item_from_text,
        get_text_from_item,
    });

    function get_users() {
        const potential_subscribers = get_potential_subscribers();
        return user_pill.filter_taken_users(potential_subscribers, pill_widget);
    }

    set_up_pill_typeahead({pill_widget, $pill_container, get_users});

    return pill_widget;
}

function get_pill_user_ids(pill_widget) {
    const user_ids = user_pill.get_user_ids(pill_widget);
    const stream_user_ids = stream_pill.get_user_ids(pill_widget);
    const group_user_ids = user_group_pill.get_user_ids(pill_widget);
    return [...user_ids, ...stream_user_ids, ...group_user_ids];
}

export function set_up_handlers({
    get_pill_widget,
    $parent_container,
    pill_selector,
    button_selector,
    action,
}) {
    /*
        This function handles events for any UI that looks like
        this:

            [pill-enabled input box for subscribers] [Add button]

        In an ideal world the above two widgets would be enclosed in
        a <form>...</form> section and we would have a single submit
        handler, but our current implementation of input pills has
        some magic that prevents the pills from playing nice with
        the vanilla HTML form/submit mechanism.

        So, instead, we provide this helper function to manage
        the two events needed to make it look like the widgets
        are inside an actual HTML <form> tag.

        This abstraction also automatically retrieves the user_ids
        from the input pill and sends them back to the `action`
        function passed in.

        The subscriber input-pill widgets lets you provide
        user_ids by creating pills for either:

            * single user
            * user group
            * stream (i.e. subscribed users for the stream)
    */
    function callback() {
        const pill_widget = get_pill_widget();
        const pill_user_ids = get_pill_user_ids(pill_widget);
        action({pill_user_ids});
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
