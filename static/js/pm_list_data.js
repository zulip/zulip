import * as pm_list from "./pm_list";

// Maximum number of conversation threads to show in default view.
const max_convos_to_show = 5;

// Maximum number of conversation threads to show in default view with unreads.
const max_convos_to_show_with_unreads = 8;

export function get_list_info(zoomed) {
    const convos = pm_list._get_convos();
    // To keep a track of number of unreads in conversation which are not shown in default view.
    let more_convos_unread_count = 0;

    let convos_to_be_shown = convos;

    if (!zoomed && convos.length > max_convos_to_show) {
        convos_to_be_shown = convos.slice(0, max_convos_to_show);

        function should_show_convo(convo) {
            if (!convos_to_be_shown.includes(convo)) {
                if (
                    convo.unread !== 0 &&
                    convos_to_be_shown.length < max_convos_to_show_with_unreads
                ) {
                    return true;
                }
                if (convo.is_active && convos_to_be_shown.length) {
                    return true;
                }
                return false;
            }
            return false;
        }

        for (const convo of convos) {
            if (should_show_convo(convo)) {
                convos_to_be_shown.push(convo);
            }
        }

        if (convos_to_be_shown.length !== convos.length) {
            convos.map((convo) => {
                if (!convos_to_be_shown.includes(convo)) {
                    more_convos_unread_count += convo.unread;
                }
                return more_convos_unread_count;
            });
        }
    }
    return {
        convos_to_be_shown,
        more_convos_unread_count,
    };
}
