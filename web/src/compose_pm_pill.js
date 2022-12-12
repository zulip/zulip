import $ from "jquery";

import * as compose_actions from "./compose_actions";
import {DirectMessageRecipientPill} from "./direct_message_recipient_pill";

export let compose_pm_pill;

export function initialize() {
    compose_pm_pill = new DirectMessageRecipientPill($("#private_message_recipient").parent());

    compose_pm_pill.widget.onPillCreate(() => {
        compose_actions.update_placeholder_text();
    });

    compose_pm_pill.widget.onPillRemove(() => {
        compose_actions.update_placeholder_text();
    });
}
