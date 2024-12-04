"use strict";

let last_issued_stream_id = 20000;

const get_stream_id = () => {
    last_issued_stream_id += 1 + Math.floor(Math.random() * 10);
    return last_issued_stream_id;
};

exports.make_stream = (opts = {}) => {
    // Since other fields are computed from these, we need to
    // pull these out of opts early.
    const stream_id = opts.stream_id ?? get_stream_id();
    const name = opts.name ?? `stream-${stream_id}`;

    const default_channel = {
        audible_notifications: false,
        /* BUG: This should always be a group ID. But it's annoying to
         * fix without assuming groups exist in the data set. */
        can_remove_subscribers_group: 0,
        can_administer_channel_group: 2,
        color: "abcd12",
        /* This is rarely going to be the case, but a valid possibility. */
        creator_id: null,
        date_created: Date.now(),
        description: `Description of ${name}`,
        desktop_notifications: false,
        email_address: "channel-email-address@example.com",
        email_notifications: false,
        /* This will rarely be the case, but is a valid possibility*/
        first_message_id: null,
        history_public_to_subscribers: true,
        invite_only: false,
        is_announcement_only: false,
        is_muted: false,
        is_web_public: false,
        message_retention_days: null,
        name,
        newly_subscribed: false,
        pin_to_top: false,
        previously_subscribed: false,
        push_notifications: false,
        render_subscribers: false,
        rendered_description: `<p>Description of ${name}</p>`,
        stream_id,
        /* STREAM_POST_POLICY_EVERYONE */
        stream_post_policy: 1,
        stream_weekly_traffic: 0,
        /* Most tests want to work with a channel the current user is subscribed to. */
        subscribed: true,
        wildcard_mentions_notify: false,
    };

    return {...default_channel, ...opts};
};
