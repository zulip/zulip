var server_events_dispatch = (function () {

var exports = {};

exports.dispatch_normal_event = function dispatch_normal_event(event) {
    var noop = function () {};
    switch (event.type) {
    case 'alert_words':
        alert_words.words = event.alert_words;
        alert_words_ui.render_alert_words_ui();
        break;

    case 'attachment':
        attachments_ui.update_attachments(event);
        break;

    case 'custom_profile_fields':
        page_params.custom_profile_fields = event.fields;
        settings_profile_fields.populate_profile_fields(page_params.custom_profile_fields);
        settings_account.add_custom_profile_fields_to_settings();
        break;

    case 'default_streams':
        stream_data.set_realm_default_streams(event.default_streams);
        settings_streams.update_default_streams_table();
        break;

    case 'delete_message':
        var msg_id = event.message_id;
        // message is passed to unread.get_unread_messages,
        // which returns all the unread messages out of a given list.
        // So double marking something as read would not occur
        unread_ops.process_read_messages_event([msg_id]);
        if (event.message_type === 'stream') {
            topic_data.remove_message({
                stream_id: event.stream_id,
                topic_name: event.topic,
            });
            stream_list.update_streams_sidebar();
        }
        ui.remove_message(msg_id);
        break;

    case 'hotspots':
        hotspots.load_new(event.hotspots);
        page_params.hotspots = page_params.hotspots ?
            page_params.hotspots.concat(event.hotspots) :
            event.hotspots;
        break;

    case 'invites_changed':
        if ($('#admin-invites-list').length) {
            settings_invites.set_up(false);
        }
        break;

    case 'muted_topics':
        muting_ui.handle_updates(event.muted_topics);
        break;

    case 'presence':
        activity.update_presence_info(event.email, event.presence, event.server_timestamp);
        break;

    case 'restart':
        var reload_options = {
            save_pointer: true,
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
        var realm_settings = {
            add_emoji_by_admins_only: settings_emoji.update_custom_emoji_ui,
            allow_edit_history: noop,
            allow_message_deleting: noop,
            allow_message_editing: noop,
            allow_community_topic_editing: noop,
            bot_creation_policy: settings_bots.update_bot_permissions_ui,
            create_stream_by_admins_only: noop,
            default_language: noop,
            default_twenty_four_hour_time: noop,
            description: noop,
            email_address_visibility: noop,
            email_changes_disabled: settings_account.update_email_change_display,
            disallow_disposable_email_addresses: noop,
            google_hangouts_domain: noop,
            inline_image_preview: noop,
            inline_url_embed_preview: noop,
            invite_by_admins_only: noop,
            invite_required: noop,
            mandatory_topics: noop,
            message_content_edit_limit_seconds: noop,
            message_content_delete_limit_seconds: noop,
            message_retention_days: noop,
            name: notifications.redraw_title,
            name_changes_disabled: settings_account.update_name_change_display,
            notifications_stream_id: noop,
            send_welcome_emails: noop,
            message_content_allowed_in_email_notifications: noop,
            signup_notifications_stream_id: noop,
            emails_restricted_to_domains: noop,
            video_chat_provider: noop,
            waiting_period_threshold: noop,
            zoom_user_id: noop,
            zoom_api_key: noop,
            zoom_api_secret: noop,
        };
        if (event.op === 'update' && _.has(realm_settings, event.property)) {
            page_params['realm_' + event.property] = event.value;
            realm_settings[event.property]();
            settings_org.sync_realm_settings(event.property);
            if (event.property === 'create_stream_by_admins_only') {
                if (!page_params.is_admin) {
                    page_params.can_create_streams =
                        !page_params.realm_create_stream_by_admins_only;
                }
            } else if (event.property === 'notifications_stream_id') {
                settings_org.render_notifications_stream_ui(
                    page_params.realm_notifications_stream_id,
                    $('#realm_notifications_stream_name'));
            } else if (event.property === 'signup_notifications_stream_id') {
                settings_org.render_notifications_stream_ui(
                    page_params.realm_signup_notifications_stream_id,
                    $('#realm_signup_notifications_stream_name'));
            }

            if (event.property === 'name' && window.electron_bridge !== undefined) {
                window.electron_bridge.send_event('realm_name', event.value);
            }
        } else if (event.op === 'update_dict' && event.property === 'default') {
            _.each(event.data, function (value, key) {
                page_params['realm_' + key] = value;
                if (key === 'allow_message_editing') {
                    message_edit.update_message_topic_editing_pencil();
                }
                if (_.has(realm_settings, key)) {
                    settings_org.sync_realm_settings(key);
                }
            });
            if (event.data.authentication_methods !== undefined) {
                settings_org.populate_auth_methods(event.data.authentication_methods);
            }
        } else if (event.op === 'update_dict' && event.property === 'icon') {
            page_params.realm_icon_url = event.data.icon_url;
            page_params.realm_icon_source = event.data.icon_source;
            realm_icon.rerender();

            var electron_bridge = window.electron_bridge;
            if (electron_bridge !== undefined) {
                electron_bridge.send_event('realm_icon_url', event.data.icon_url);
            }
        } else if (event.op === 'update_dict' && event.property === 'logo') {
            page_params.realm_logo_url = event.data.logo_url;
            page_params.realm_logo_source = event.data.logo_source;
            realm_logo.rerender();
        } else if (event.op === 'update_dict' && event.property === 'night_logo') {
            page_params.realm_night_logo_url = event.data.night_logo_url;
            page_params.realm_night_logo_source = event.data.night_logo_source;
            realm_logo.rerender();
        } else if (event.op === 'deactivated') {
            window.location.href = "/accounts/deactivated/";
        }

        break;

    case 'realm_bot':
        if (event.op === 'add') {
            bot_data.add(event.bot);
            settings_users.update_user_data(event.bot.user_id, event.bot);
        } else if (event.op === 'remove') {
            bot_data.deactivate(event.bot.user_id);
            event.bot.is_active = false;
            settings_users.update_user_data(event.bot.user_id, event.bot);
        } else if (event.op === 'delete') {
            bot_data.delete(event.bot.user_id);
            settings_users.update_user_data(event.bot.user_id, event.bot);
        } else if (event.op === 'update') {
            if (_.has(event.bot, 'owner_id')) {
                event.bot.owner = people.get_person_from_user_id(event.bot.owner_id).email;
            }
            bot_data.update(event.bot.user_id, event.bot);
            settings_users.update_user_data(event.bot.user_id, event.bot);
        }
        break;

    case 'realm_emoji':
        // Update `page_params.realm_emoji` so that settings page
        // can display it properly when reopened without refresh.
        page_params.realm_emoji = event.realm_emoji;
        emoji.update_emojis(event.realm_emoji);
        settings_emoji.populate_emoji(event.realm_emoji);
        emoji_picker.generate_emoji_picker_data(emoji.active_realm_emojis);
        composebox_typeahead.update_emoji_data();
        break;

    case 'realm_filters':
        page_params.realm_filters = event.realm_filters;
        markdown.set_realm_filters(page_params.realm_filters);
        settings_linkifiers.populate_filters(page_params.realm_filters);
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
            stream_events.remove_deactivated_user_from_all_streams(event.person.user_id);
        } else if (event.op === 'update') {
            user_events.update_person(event.person);
        }
        break;

    case 'stream':
        if (event.op === 'update') {
            // Legacy: Stream properties are still managed by subs.js on the client side.
            stream_events.update_property(
                event.stream_id,
                event.property,
                event.value,
                event.rendered_description
            );
            settings_streams.update_default_streams_table();
        } else if (event.op === 'create') {
            stream_data.create_streams(event.streams);
            _.each(event.streams, function (stream) {
                var sub = stream_data.get_sub_by_id(stream.stream_id);
                stream_data.update_calculated_fields(sub);
                subs.add_sub_to_table(sub);
            });
        } else if (event.op === 'delete') {
            _.each(event.streams, function (stream) {
                var was_subscribed = stream_data.get_sub_by_id(stream.stream_id).subscribed;
                subs.remove_stream(stream.stream_id);
                stream_data.delete_sub(stream.stream_id);
                if (was_subscribed) {
                    stream_list.remove_sidebar_row(stream.stream_id);
                }
                settings_streams.remove_default_stream(stream.stream_id);
                stream_data.remove_default_stream(stream.stream_id);
                if (page_params.realm_notifications_stream_id === stream.stream_id) {
                    page_params.realm_notifications_stream_id = -1;
                    settings_org.render_notifications_stream_ui(
                        page_params.realm_notifications_stream_id,
                        $('#realm_notifications_stream_name'));
                }
                if (page_params.realm_signup_notifications_stream_id === stream.stream_id) {
                    page_params.realm_signup_notifications_stream_id = -1;
                    settings_org.render_notifications_stream_ui(
                        page_params.realm_signup_notifications_stream_id,
                        $('#realm_signup_notifications_stream_name'));
                }
            });
        }
        break;

    case 'submessage':
        // The fields in the event don't quite exactly
        // match the layout of a submessage, since there's
        // an event id.  We also want to be explicit here.
        var submsg = {
            id: event.submessage_id,
            sender_id: event.sender_id,
            msg_type: event.msg_type,
            message_id: event.message_id,
            content: event.content,
        };
        submessage.handle_event(submsg);
        break;

    case 'subscription':
        if (event.op === 'add') {
            _.each(event.subscriptions, function (rec) {
                var sub = stream_data.get_sub_by_id(rec.stream_id);
                if (sub) {
                    stream_data.update_stream_email_address(sub, rec.email_address);
                    stream_events.mark_subscribed(sub, rec.subscribers, rec.color);
                } else {
                    blueslip.error('Subscribing to unknown stream with ID ' + rec.stream_id);
                }
            });
        } else if (event.op === 'peer_add') {
            _.each(event.subscriptions, function (sub) {
                if (stream_data.add_subscriber(sub, event.user_id)) {
                    $(document).trigger('peer_subscribe.zulip', {stream_name: sub});
                } else {
                    blueslip.warn('Cannot process peer_add event');
                }
            });
        } else if (event.op === 'peer_remove') {
            _.each(event.subscriptions, function (sub) {
                if (stream_data.remove_subscriber(sub, event.user_id)) {
                    $(document).trigger('peer_unsubscribe.zulip', {stream_name: sub});
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
        var user_display_settings = [
            'default_language',
            'dense_mode',
            'emojiset',
            'high_contrast_mode',
            'night_mode',
            'left_side_userlist',
            'timezone',
            'twenty_four_hour_time',
            'translate_emoticons',
            'starred_message_counts',
        ];
        if (_.contains(user_display_settings, event.setting_name)) {
            page_params[event.setting_name] = event.setting;
        }
        if (event.setting_name === 'default_language') {
            // We additionally need to set the language name.
            page_params.default_language_name = event.language_name;
        }
        if (event.setting_name === 'twenty_four_hour_time') {
            // Rerender the whole message list UI
            home_msg_list.rerender();
            if (current_msg_list === message_list.narrowed) {
                message_list.narrowed.rerender();
            }
        }
        if (event.setting_name === 'high_contrast_mode') {
            $("body").toggleClass("high-contrast");
        }
        if (event.setting_name === 'dense_mode') {
            $("body").toggleClass("less_dense_mode");
            $("body").toggleClass("more_dense_mode");
        }
        if (event.setting_name === 'night_mode') {
            $("body").fadeOut(300);
            setTimeout(function () {
                if (event.setting === true) {
                    night_mode.enable();
                    realm_logo.rerender();
                } else {
                    night_mode.disable();
                    realm_logo.rerender();
                }
                $("body").fadeIn(300);
            }, 300);
        }
        if (event.setting_name === 'starred_message_counts') {
            starred_messages.rerender_ui();
        }
        if (event.setting_name === 'left_side_userlist') {
            // TODO: Make this change the view immediately rather
            // than requiring a reload or page resize.
        }
        if (event.setting_name === 'default_language') {
            // TODO: Make this change the view immediately rather
            // than requiring a reload or page resize.
        }
        if (event.setting_name === 'emojiset') {
            settings_display.report_emojiset_change();

            // Rerender the whole message list UI
            home_msg_list.rerender();
            if (current_msg_list === message_list.narrowed) {
                message_list.narrowed.rerender();
            }
        }
        settings_display.update_page();
        break;

    case 'update_global_notifications':
        notifications.handle_global_notification_updates(event.notification_name,
                                                         event.setting);
        settings_notifications.update_page();
        break;

    case 'update_message_flags':
        var new_value = event.operation === "add";
        switch (event.flag) {
        case 'starred':
            _.each(event.messages, function (message_id) {
                message_flags.update_starred_flag(message_id, new_value);
            });
            if (event.operation === "add") {
                starred_messages.add(event.messages);
            } else {
                starred_messages.remove(event.messages);
            }
            break;
        case 'read':
            unread_ops.process_read_messages_event(event.messages);
            break;
        }
        break;

    case 'user_group':
        if (event.op === 'add') {
            user_groups.add(event.group);
        } else if (event.op === 'add_members') {
            user_groups.add_members(event.group_id, event.user_ids);
        } else if (event.op === 'remove_members') {
            user_groups.remove_members(event.group_id, event.user_ids);
        } else if (event.op === "update") {
            user_groups.update(event);
        }
        settings_user_groups.reload();
        break;

    case 'user_status':
        if (event.away !== undefined) {
            if (event.away) {
                activity.on_set_away(event.user_id);
            } else {
                activity.on_revoke_away(event.user_id);
            }
        }

        if (event.status_text !== undefined) {
            user_status.set_status_text({
                user_id: event.user_id,
                status_text: event.status_text,
            });
            activity.redraw_user(event.user_id);
        }
        break;
    }

};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = server_events_dispatch;
}
window.server_events_dispatch = server_events_dispatch;
