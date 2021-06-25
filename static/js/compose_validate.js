import $ from "jquery";

import * as compose from "./compose";
import * as compose_error from "./compose_error";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_state from "./compose_state";
import {$t, $t_html} from "./i18n";
import {page_params} from "./page_params";
import * as people from "./people";
import * as reminder from "./reminder";
import * as stream_data from "./stream_data";
import * as util from "./util";

function validate_stream_message() {
    const stream_name = compose_state.stream_name();
    if (stream_name === "") {
        compose_error.show(
            $t_html({defaultMessage: "Please specify a stream"}),
            $("#stream_message_recipient_stream"),
        );
        return false;
    }

    if (page_params.realm_mandatory_topics) {
        const topic = compose_state.topic();
        if (topic === "") {
            compose_error.show(
                $t_html({defaultMessage: "Please specify a topic"}),
                $("#stream_message_recipient_topic"),
            );
            return false;
        }
    }

    const sub = stream_data.get_sub(stream_name);
    if (!sub) {
        return compose.validation_error("does-not-exist", stream_name);
    }

    if (!compose.validate_stream_message_post_policy(sub)) {
        return false;
    }

    /* Note: This is a global and thus accessible in the functions
       below; it's important that we update this state here before
       proceeding with further validation. */
    compose.set_wildcard_mention(util.find_wildcard_mentions(compose_state.message_content()));

    // If both `@all` is mentioned and it's in `#announce`, just validate
    // for `@all`. Users shouldn't have to hit "yes" more than once.
    if (compose.wildcard_mention !== null && stream_name === "announce") {
        if (
            !compose.validate_stream_message_address_info(stream_name) ||
            !compose.validate_stream_message_mentions(sub.stream_id)
        ) {
            return false;
        }
        // If either criteria isn't met, just do the normal validation.
    } else {
        if (
            !compose.validate_stream_message_address_info(stream_name) ||
            !compose.validate_stream_message_mentions(sub.stream_id) ||
            !compose.validate_stream_message_announce(sub)
        ) {
            return false;
        }
    }

    return true;
}

// The function checks whether the recipients are users of the realm or cross realm users (bots
// for now)
function validate_private_message() {
    if (page_params.realm_private_message_policy === 2) {
        // Frontend check for for PRIVATE_MESSAGE_POLICY_DISABLED
        const user_ids = compose_pm_pill.get_user_ids();
        if (user_ids.length !== 1 || !people.get_by_user_id(user_ids[0]).is_bot) {
            // Unless we're composing to a bot
            compose_error.show(
                $t_html({defaultMessage: "Private messages are disabled in this organization."}),
                $("#private_message_recipient"),
            );
            return false;
        }
    }

    if (compose_state.private_message_recipient().length === 0) {
        compose_error.show(
            $t_html({defaultMessage: "Please specify at least one valid recipient"}),
            $("#private_message_recipient"),
        );
        return false;
    } else if (page_params.realm_is_zephyr_mirror_realm) {
        // For Zephyr mirroring realms, the frontend doesn't know which users exist
        return true;
    }

    const invalid_recipients = compose.get_invalid_recipient_emails();

    let context = {};
    if (invalid_recipients.length === 1) {
        context = {recipient: invalid_recipients.join(",")};
        compose_error.show(
            $t_html({defaultMessage: "The recipient {recipient} is not valid"}, context),
            $("#private_message_recipient"),
        );
        return false;
    } else if (invalid_recipients.length > 1) {
        context = {recipients: invalid_recipients.join(",")};
        compose_error.show(
            $t_html({defaultMessage: "The recipients {recipients} are not valid"}, context),
            $("#private_message_recipient"),
        );
        return false;
    }
    return true;
}

export function validate() {
    $("#compose-send-button").prop("disabled", true).trigger("blur");
    const message_content = compose_state.message_content();
    if (reminder.is_deferred_delivery(message_content)) {
        compose.show_sending_indicator($t({defaultMessage: "Scheduling..."}));
    } else {
        compose.show_sending_indicator($t({defaultMessage: "Sending..."}));
    }

    if (/^\s*$/.test(message_content)) {
        compose_error.show(
            $t_html({defaultMessage: "You have nothing to send!"}),
            $("#compose-textarea"),
        );
        return false;
    }

    if ($("#zephyr-mirror-error").is(":visible")) {
        compose_error.show(
            $t_html({
                defaultMessage:
                    "You need to be running Zephyr mirroring in order to send messages!",
            }),
        );
        return false;
    }

    if (compose_state.get_message_type() === "private") {
        return validate_private_message();
    }
    return validate_stream_message();
}
