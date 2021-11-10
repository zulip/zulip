import * as poll_common_function from "./poll_widget_common";

export function activate({elem, callback, extra_data, message}) {
    poll_common_function.activate({elem, callback, extra_data, message, anonymous_poll: true});
}
