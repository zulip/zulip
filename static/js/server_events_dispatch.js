var server_events_dispatch = (function () {

var exports = {};

exports.dispatch_normal_event = function dispatch_normal_event(event) {
    switch (event.type) {
    case 'alert_words':
        alert_words.words = event.alert_words;
        break;

    case 'default_streams':
        page_params.realm_default_streams = event.default_streams;
        settings_streams.update_default_streams_table();
        break;

    case 'hotspots':
        hotspots.show(event.hotspots);
        page_params.hotspots = event.hotspots;
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
        } else if (event.op === 'update' && event.property === 'description') {
            page_params.realm_description = event.value;
            settings_org.update_realm_description(event.value);
        } else if (event.op === 'update' && event.property === 'invite_required') {
            page_params.realm_invite_required = event.value;
        } else if (event.op === 'update' && event.property === 'invite_by_admins_only') {
            page_params.realm_invite_by_admins_only = event.value;
        } else if (event.op === 'update' && event.property === 'inline_image_preview') {
            page_params.realm_inline_image_preview = event.value;
        } else if (event.op === 'update' && event.property === 'inline_url_embed_preview') {
            page_params.realm_inline_url_embed_preview = event.value;
        } else if (event.op === 'update' && event.property === 'create_stream_by_admins_only') {
            page_params.realm_create_stream_by_admins_only = event.value;
            if (!page_params.is_admin) {
                page_params.can_create_streams = !page_params.realm_create_stream_by_admins_only;
            }
        } else if (event.op === 'update' && event.property === 'name_changes_disabled') {
            page_params.realm_name_changes_disabled = event.value;
            settings_org.toggle_name_change_display();
        } else if (event.op === 'update' && event.property === 'email_changes_disabled') {
            page_params.realm_email_changes_disabled = event.value;
            settings_org.toggle_email_change_display();
        } else if (event.op === 'update' && event.property === 'add_emoji_by_admins_only') {
            page_params.add_emoji_by_admins_only = event.value;
        } else if (event.op === 'update' && event.property === 'restricted_to_domain') {
            page_params.realm_restricted_to_domain = event.value;
        } else if (event.op === 'update' && event.property === 'message_retention_days') {
            page_params.message_retention_days = event.value;
            settings_org.update_message_retention_days();
        } else if (event.op === 'update_dict' && event.property === 'default') {
            $.each(event.data, function (key, value) {
                page_params['realm_' + key] = value;
            });
            if (event.data.authentication_methods !== undefined) {
                settings_org.populate_auth_methods(event.data.authentication_methods);
            }
        } else if (event.op === 'update' && event.property === 'default_language') {
            page_params.realm_default_language = event.value;
            settings_org.reset_realm_default_language();
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
            settings_users.update_user_data(event.bot.user_id, event.bot);
        } else if (event.op === 'remove') {
            bot_data.deactivate(event.bot.email);
            event.bot.is_active = false;
            settings_users.update_user_data(event.bot.user_id, event.bot);
        } else if (event.op === 'update') {
            if (_.has(event.bot, 'owner_id')) {
                event.bot.owner = people.get_person_from_user_id(event.bot.owner_id).email;
            }
            bot_data.update(event.bot.email, event.bot);
            settings_users.update_user_data(event.bot.user_id, event.bot);
        }
        break;

    case 'realm_emoji':
        // Update `page_params.realm_emoji` so that settings page
        // can display it properly when reopened without refresh.
        page_params.realm_emoji = event.realm_emoji;
        emoji.update_emojis(event.realm_emoji);
        settings_emoji.populate_emoji(event.realm_emoji);
        break;

    case 'realm_filters':
        page_params.realm_filters = event.realm_filters;
        markdown.set_realm_filters(page_params.realm_filters);
        settings_filters.populate_filters(page_params.realm_filters);
        break;

    case 'realm_domains':
        var i;
        if (event.op === 'add') {
            page_params.realm_domains.push(event.realm_domain);
        } else if (event.op === 'change') {
            for (i = 0; i < page_params.realm_domains.length; i += 1) {
                if (page_params.realm_domains[i].domain === event.realm_domain.domain) {
                    page_params.realm_domains[i].allow_subdomains =
                        event.realm_domain.allow_subdomains;
                    break;
                }
            }
        } else if (event.op === 'remove') {
            for (i = 0; i < page_params.realm_domains.length; i += 1) {
                if (page_params.realm_domains[i].domain === event.domain) {
                    page_params.realm_domains.splice(i, 1);
                    break;
                }
            }
        }
        settings_org.populate_realm_domains(page_params.realm_domains);
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
            stream_events.update_property(
                event.stream_id,
                event.property,
                event.value
            );
            settings_streams.update_default_streams_table();
        } else if (event.op === 'create') {
            stream_data.create_streams(event.streams);
        } else if (event.op === 'delete') {
            _.each(event.streams, function (stream) {
                if (stream_data.is_subscribed(stream.name)) {
                    stream_list.remove_sidebar_row(stream.stream_id);
                }
                subs.remove_stream(stream.stream_id);
                stream_data.delete_sub(stream.stream_id);
                settings_streams.remove_default_stream(stream.stream_id);
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
                    stream_events.mark_subscribed(sub, rec.subscribers);
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
                stream_events.mark_unsubscribed(sub);
            });
        } else if (event.op === 'update') {
            stream_events.update_property(
                event.stream_id,
                event.property,
                event.value
            );
        }
        break;

    case 'typing':
        if (event.sender.user_id === page_params.user_id) {
            // typing notifications are sent to the user who is typing
            // as well as recipients; we ignore such self-generated events.
            return;
        }

        if (event.op === 'start') {
            typing_events.display_notification(event);
        } else if (event.op === 'stop') {
            typing_events.hide_notification(event);
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
        if (event.setting_name === 'timezone') {
            page_params.timezone = event.setting;
        }
        if (event.setting_name === 'emojiset') {
            page_params.emojiset = event.setting;
            var sprite = new Image();
            sprite.onload = function () {
                $("#emoji-spritesheet").attr('href', "/static/generated/emoji/" + page_params.emojiset + "_sprite.css");
                if ($("#display-settings-status").length) {
                    loading.destroy_indicator($("#emojiset_spinner"));
                    $("#emojiset_select").val(page_params.emojiset);
                    ui_report.success(i18n.t("Emojiset changed successfully!!"),
                                      $('#display-settings-status').expectOne());
                }
            };
            sprite.src = "/static/generated/emoji/sheet_" + page_params.emojiset + "_32.png";
        }
        if ($("#settings.tab-pane.active").length) {
            settings_display.update_page();
        }
        break;

    case 'update_global_notifications':
        notifications.handle_global_notification_updates(event.notification_name,
                                                         event.setting);
        if ($("#settings.tab-pane.active").length) {
            settings_notifications.update_page();
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
            unread_ops.mark_messages_as_read(msgs_to_update, {from: "server"});
            break;
        }
        break;

    case 'delete_message':
        var msg_id = event.message_id;
        ui.remove_message(msg_id);
        break;

    }
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = server_events_dispatch;
}
