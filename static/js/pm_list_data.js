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
        // If we are in default view and we get the length of convos > max_convos_to_show, we use the same algorithm
        // as we use in topics data list to decide the number of conversations to display in default view.
        convos_to_be_shown = convos.slice(0, max_convos_to_show);

        function should_show_convo(convo) {
            // A function to check whether should we include the conversation in default view after
            // the conversations length exceeding max_convos_to_show.
            if (!convos_to_be_shown.includes(convo)) {
                // If a conversation has a unread and also at the same time the length of conversations to show
                // have not exceeded max_convos_to_show_with_unreads we append the conversation inside the default view itself.
                if (
                    convo.unread !== 0 &&
                    convos_to_be_shown.length < max_convos_to_show_with_unreads
                ) {
                    return true;
                }

                // lastly, we always need to append the active conversation(if not present) at the end of list of default view
                // conversations, irrespective of the length of default view conversations.
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
            // whenever we have total number of conversations to show greater than that which are being shown in default view
            // we calculate the number of unreads present in those remaining conversations and return it to display with
            // `more conversations` li-item.
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
