import $ from "jquery";

export function get_edit_container(sub) {
    return $(
        `#subscription_overlay .subscription_settings[data-stream-id='${CSS.escape(
            sub.stream_id,
        )}']`,
    );
}
