var server_events = (function () {

var exports = {};

var waiting_on_homeview_load = true;

var events_stored_during_tutorial = [];
var events_stored_while_loading = [];

var get_events_xhr;
var get_events_timeout;
var get_events_failures = 0;
var get_events_params = {};

function dispatch_normal_event(event) {
    switch (event.type) {
    case 'alert_words':
        alert_words.words = event.alert_words;
        break;

    case 'default_streams':
        page_params.realm_default_streams = event.default_streams;
        admin.update_default_streams_table();
        break;

    case 'muted_topics':
        muting_ui.handle_updates(event.muted_topics);
        break;

    case 'presence':
        activity.set_user_status(event.email, event.presence, event.server_timestamp);
        break;

    case 'restart':
        var reload_options = {save_pointer: true,
                              save_narrow: true,
                              save_compose: true,
                              message: "The application has been updated; reloading!",
                             };
        if (event.immediate) {
            reload_options.immediate = true;
        }
        reload.initiate(reload_options);
        break;

    case 'reaction':
        if (event.op === 'add') {
            reactions.add_reaction(event);
        } else if (event.op === 'remove') {
            reactions.remove_reaction(event);
        }
        break;

    case 'realm':
        if (event.op === 'update' && event.property === 'name') {
            page_params.realm_name = event.value;
            notifications.redraw_title();
        } else if (event.op === 'update' && event.property === 'invite_required') {
            page_params.realm_invite_required = event.value;
        } else if (event.op === 'update' && event.property === 'invite_by_admins_only') {
            page_params.realm_invite_by_admins_only = event.value;
        } else if (event.op === 'update' && event.property === 'create_stream_by_admins_only') {
            page_params.realm_create_stream_by_admins_only = event.value;
            if (!page_params.is_admin) {
                page_params.can_create_streams = !page_params.realm_create_stream_by_admins_only;
            }
        } else if (event.op === 'update' && event.property === 'name_changes_disabled') {
            page_params.realm_name_changes_disabled = event.value;
            admin.toggle_name_change_display();
        } else if (event.op === 'update' && event.property === 'email_changes_disabled') {
            page_params.realm_email_changes_disabled = event.value;
            admin.toggle_email_change_display();
        } else if (event.op === 'update' && event.property === 'add_emoji_by_admins_only') {
            page_params.add_emoji_by_admins_only = event.value;
        } else if (event.op === 'update' && event.property === 'restricted_to_domain') {
            page_params.realm_restricted_to_domain = event.value;
        } else if (event.op === 'update_dict' && event.property === 'default') {
            $.each(event.data, function (key, value) {
                page_params['realm_' + key] = value;
            });
            if (event.data.authentication_methods !== undefined) {
                admin.populate_auth_methods(event.data.authentication_methods);
            }
        } else if (event.op === 'update' && event.property === 'default_language') {
            page_params.realm_default_language = event.value;
            admin.reset_realm_default_language();
        } else if (event.op === 'update' && event.property === 'waiting_period_threshold') {
            page_params.realm_waiting_period_threshold = event.value;
        } else if (event.op === 'update_dict' && event.property === 'icon') {
            page_params.realm_icon_url = event.data.icon_url;
            page_params.realm_icon_source = event.data.icon_source;
            realm_icon.rerender();
        }

        break;

    case 'realm_bot':
        if (event.op === 'add') {
            bot_data.add(event.bot);
        } else if (event.op === 'remove') {
            bot_data.deactivate(event.bot.email);
        } else if (event.op === 'update') {
            if (_.has(event.bot, 'owner_id')) {
                event.bot.owner = people.get_person_from_user_id(event.bot.owner_id).email;
            }
            bot_data.update(event.bot.email, event.bot);
            admin.update_user_data(event.bot.user_id, event.bot);
        }
        break;

    case 'realm_emoji':
        emoji.update_emojis(event.realm_emoji);
        admin.populate_emoji(event.realm_emoji);
        break;

    case 'realm_filters':
        page_params.realm_filters = event.realm_filters;
        echo.set_realm_filters(page_params.realm_filters);
        admin.populate_filters(page_params.realm_filters);
        break;

    case 'realm_domains':
        var i;
        if (event.op === 'add') {
            page_params.domains.push(event.alias);
        } else if (event.op === 'change') {
            for (i = 0; i < page_params.domains.length; i += 1) {
                if (page_params.domains[i].domain === event.alias.domain) {
                    page_params.domains[i].allow_subdomains = event.alias.allow_subdomains;
                    break;
                }
            }
        } else if (event.op === 'remove') {
            for (i = 0; i < page_params.domains.length; i += 1) {
                if (page_params.domains[i].domain === event.domain) {
                    page_params.domains.splice(i, 1);
                    break;
                }
            }
        }
        admin.populate_realm_aliases(page_params.domains);
        break;

    case 'realm_user':
        if (event.op === 'add') {
            people.add_in_realm(event.person);
        } else if (event.op === 'remove') {
            people.deactivate(event.person);
        } else if (event.op === 'update') {
            user_events.update_person(event.person);
        }
        break;

    case 'referral':
        referral.update_state(event.referrals.granted, event.referrals.used);
        break;

    case 'stream':
        if (event.op === 'update') {
            // Legacy: Stream properties are still managed by subs.js on the client side.
            subs.update_subscription_properties(
                event.stream_id,
                event.property,
                event.value
            );
            admin.update_default_streams_table();
        } else if (event.op === 'create') {
            stream_data.create_streams(event.streams);
        } else if (event.op === 'delete') {
            _.each(event.streams, function (stream) {
                if (stream_data.is_subscribed(stream.name)) {
                    stream_list.remove_sidebar_row(stream.stream_id);
                }
                subs.remove_stream(stream.stream_id);
                stream_data.delete_sub(stream.stream_id);
                admin.remove_default_stream(stream.stream_id);
                stream_data.remove_default_stream(stream.stream_id);
            });
        }
        break;

    case 'subscription':
        var person;
        var email;

        if (event.op === 'add') {
            _.each(event.subscriptions, function (rec) {
                var sub = stream_data.get_sub_by_id(rec.stream_id);
                if (sub) {
                    subs.mark_subscribed(sub, rec.subscribers);
                } else {
                    blueslip.error('Subscribing to unknown stream' + rec.stream_id);
                }
            });
        } else if (event.op === 'peer_add') {
            // TODO: remove email shim here and fix called functions
            //       to use user_ids
            person = people.get_person_from_user_id(event.user_id);
            email = person.email;
            _.each(event.subscriptions, function (sub) {
                if (stream_data.add_subscriber(sub, event.user_id)) {
                    $(document).trigger(
                        'peer_subscribe.zulip',
                        {stream_name: sub, user_email: email});
                } else {
                    blueslip.warn('Cannot process peer_add event');
                }
            });
        } else if (event.op === 'peer_remove') {
            // TODO: remove email shim here and fix called functions
            //       to use user_ids
            person = people.get_person_from_user_id(event.user_id);
            email = person.email;
            _.each(event.subscriptions, function (sub) {
                if (stream_data.remove_subscriber(sub, event.user_id)) {
                    $(document).trigger(
                        'peer_unsubscribe.zulip',
                        {stream_name: sub, user_email: email});
                } else {
                    blueslip.warn('Cannot process peer_remove event.');
                }
            });
        } else if (event.op === 'remove') {
            _.each(event.subscriptions, function (rec) {
                var sub = stream_data.get_sub_by_id(rec.stream_id);
                subs.mark_sub_unsubscribed(sub);
            });
        } else if (event.op === 'update') {
            subs.update_subscription_properties(
                event.stream_id,
                event.property,
                event.value
            );
        }
        break;

    case 'update_display_settings':
        if (event.setting_name === 'twenty_four_hour_time') {
            page_params.twenty_four_hour_time = event.setting;
            // Rerender the whole message list UI
            home_msg_list.rerender();
            if (current_msg_list === message_list.narrowed) {
                message_list.narrowed.rerender();
            }
        }
        if (event.setting_name === 'emoji_alt_code') {
            page_params.emoji_alt_code = event.setting;
            // Rerender the whole message list UI
            home_msg_list.rerender();
            if (current_msg_list === message_list.narrowed) {
                message_list.narrowed.rerender();
            }
        }
        if (event.setting_name === 'left_side_userlist') {
            // TODO: Make this change the view immediately rather
            // than requiring a reload or page resize.
            page_params.left_side_userlist = event.setting;
        }
        if (event.setting_name === 'default_language') {
            // TODO: Make this change the view immediately rather
            // than requiring a reload or page resize.
            page_params.default_language = event.setting;
        }
        if ($("#settings.tab-pane.active").length) {
            settings.update_page();
        }
        break;

    case 'update_global_notifications':
        notifications.handle_global_notification_updates(event.notification_name,
                                                         event.setting);
        if ($("#settings.tab-pane.active").length) {
            settings.update_page();
        }
        break;

    case 'update_message_flags':
        var new_value = event.operation === "add";
        switch (event.flag) {
        case 'starred':
            _.each(event.messages, function (message_id) {
                ui.update_starred(message_id, new_value);
            });
            break;
        case 'read':
            var msgs_to_update = _.map(event.messages, function (message_id) {
                return message_store.get(message_id);
            });
            unread_ui.mark_messages_as_read(msgs_to_update, {from: "server"});
            break;
        }
        break;
    }
}

function get_events_success(events) {
    var messages = [];
    var messages_to_update = [];
    var new_pointer;

    var clean_event = function clean_event(event) {
        // Only log a whitelist of the event to remove private data
        return _.pick(event, 'id', 'type', 'op');
    };

    _.each(events, function (event) {
        try {
            get_events_params.last_event_id = Math.max(get_events_params.last_event_id,
                                                       event.id);
        } catch (ex) {
            blueslip.error('Failed to update last_event_id',
                           {event: clean_event(event)},
                           ex.stack);
        }
    });

    if (tutorial.is_running()) {
        events_stored_during_tutorial = events_stored_during_tutorial.concat(events);
        return;
    }

    if (events_stored_during_tutorial.length > 0) {
        events = events_stored_during_tutorial.concat(events);
        events_stored_during_tutorial = [];
    }

    if (waiting_on_homeview_load) {
        events_stored_while_loading = events_stored_while_loading.concat(events);
        return;
    }

    if (events_stored_while_loading.length > 0) {
        events = events_stored_while_loading.concat(events);
        events_stored_while_loading = [];
    }

    var dispatch_event = function dispatch_event(event) {
        switch (event.type) {
        case 'message':
            var msg = event.message;
            msg.flags = event.flags;
            if (event.local_message_id !== undefined) {
                msg.local_id = event.local_message_id;
            }
            messages.push(msg);
            break;

        case 'pointer':
            new_pointer = event.pointer;
            break;

        case 'update_message':
            messages_to_update.push(event);
            break;

        default:
            return dispatch_normal_event(event);
        }
    };

    _.each(events, function (event) {
        try {
            dispatch_event(event);
        } catch (ex1) {
            blueslip.error('Failed to process an event\n' +
                           blueslip.exception_msg(ex1),
                           {event: clean_event(event)},
                           ex1.stack);
        }
    });

    if (messages.length !== 0) {
        try {
            messages = echo.process_from_server(messages);
            message_store.insert_new_messages(messages);
        } catch (ex2) {
            blueslip.error('Failed to insert new messages\n' +
                           blueslip.exception_msg(ex2),
                           undefined,
                           ex2.stack);
        }
    }

    if (new_pointer !== undefined
        && new_pointer > pointer.furthest_read) {
        pointer.furthest_read = new_pointer;
        pointer.server_furthest_read = new_pointer;
        home_msg_list.select_id(new_pointer, {then_scroll: true, use_closest: true});
    }

    if ((home_msg_list.selected_id() === -1) && !home_msg_list.empty()) {
        home_msg_list.select_id(home_msg_list.first().id, {then_scroll: false});
    }

    if (messages_to_update.length !== 0) {
        try {
            message_store.update_messages(messages_to_update);
        } catch (ex3) {
            blueslip.error('Failed to update messages\n' +
                           blueslip.exception_msg(ex3),
                           undefined,
                           ex3.stack);
        }
    }
}

function get_events(options) {
    options = _.extend({dont_block: false}, options);

    if (reload.is_in_progress()) {
        return;
    }

    get_events_params.dont_block = options.dont_block || get_events_failures > 0;
    if (get_events_params.queue_id === undefined) {
        get_events_params.queue_id = page_params.event_queue_id;
        get_events_params.last_event_id = page_params.last_event_id;
    }

    if (get_events_xhr !== undefined) {
        get_events_xhr.abort();
    }
    if (get_events_timeout !== undefined) {
        clearTimeout(get_events_timeout);
    }
    get_events_timeout = undefined;
    get_events_xhr = channel.get({
        url:      '/json/events',
        data:     get_events_params,
        idempotent: true,
        timeout:  page_params.poll_timeout,
        success: function (data) {
            try {
                get_events_xhr = undefined;
                get_events_failures = 0;
                $('#connection-error').hide();

                get_events_success(data.events);
            } catch (ex) {
                blueslip.error('Failed to handle get_events success\n' +
                               blueslip.exception_msg(ex),
                               undefined,
                               ex.stack);
            }
            get_events_timeout = setTimeout(get_events, 0);
        },
        error: function (xhr, error_type) {
            try {
                get_events_xhr = undefined;
                // If we are old enough to have messages outside of the
                // Tornado cache or if we're old enough that our message
                // queue has been garbage collected, immediately reload.
                if ((xhr.status === 400) &&
                    (JSON.parse(xhr.responseText).msg.indexOf("too old") !== -1 ||
                     JSON.parse(xhr.responseText).msg.indexOf("Bad event queue id") !== -1)) {
                    page_params.event_queue_expired = true;
                    reload.initiate({immediate: true,
                                     save_pointer: false,
                                     save_narrow: false,
                                     save_compose: true});
                }

                if (error_type === 'abort') {
                    // Don't restart if we explicitly aborted
                    return;
                } else if (error_type === 'timeout') {
                    // Retry indefinitely on timeout.
                    get_events_failures = 0;
                    $('#connection-error').hide();
                } else {
                    get_events_failures += 1;
                }

                if (get_events_failures >= 5) {
                    $('#connection-error').show();
                } else {
                    $('#connection-error').hide();
                }
            } catch (ex) {
                blueslip.error('Failed to handle get_events error\n' +
                               blueslip.exception_msg(ex),
                               undefined,
                               ex.stack);
            }
            var retry_sec = Math.min(90, Math.exp(get_events_failures/2));
            get_events_timeout = setTimeout(get_events, retry_sec*1000);
        },
    });
}

exports.assert_get_events_running = function assert_get_events_running(error_message) {
    if (get_events_xhr === undefined && get_events_timeout === undefined) {
        exports.restart_get_events({dont_block: true});
        blueslip.error(error_message);
    }
};

exports.restart_get_events = function restart_get_events(options) {
    get_events(options);
};

exports.force_get_events = function force_get_events() {
    get_events_timeout = setTimeout(get_events, 0);
};

exports.home_view_loaded = function home_view_loaded() {
    waiting_on_homeview_load = false;
    get_events_success([]);
    $(document).trigger("home_view_loaded.zulip");
};

var watchdog_time = $.now();
setInterval(function () {
    var new_time = $.now();
    if ((new_time - watchdog_time) > 20000) { // 20 seconds.
        // Defensively reset watchdog_time here in case there's an
        // exception in one of the event handlers
        watchdog_time = new_time;
        // Our app's JS wasn't running, which probably means the machine was
        // asleep.
        $(document).trigger($.Event('unsuspend'));
    }
    watchdog_time = new_time;
}, 5000);

util.execute_early(function () {
    $(document).on('unsuspend', function () {
        // Immediately poll for new events on unsuspend
        blueslip.log("Restarting get_events due to unsuspend");
        get_events_failures = 0;
        exports.restart_get_events({dont_block: true});
    });
    get_events();
});

exports.cleanup_event_queue = function cleanup_event_queue() {
    // Submit a request to the server to cleanup our event queue
    if (page_params.event_queue_expired === true) {
        return;
    }
    // Set expired because in a reload we may be called twice.
    page_params.event_queue_expired = true;
    channel.del({
        url:      '/json/events',
        data:     {queue_id: page_params.event_queue_id},
    });
};

window.addEventListener("beforeunload", function () {
    exports.cleanup_event_queue();
});

// For unit testing
exports._get_events_success = get_events_success;

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = server_events;
}
