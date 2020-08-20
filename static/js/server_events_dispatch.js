"use strict";

const emoji = require("../shared/js/emoji");

const people = require("./people");
const settings_config = require("./settings_config");

exports.dispatch_normal_event = function dispatch_normal_event(event) {
    const noop = function () {};
    switch (event.type) {
        case "alert_words":
            alert_words.set_words(event.alert_words);
            alert_words_ui.render_alert_words_ui();
            break;

        case "attachment":
            attachments_ui.update_attachments(event);
            break;

        case "custom_profile_fields":
            page_params.custom_profile_fields = event.fields;
            settings_profile_fields.populate_profile_fields(page_params.custom_profile_fields);
            settings_account.add_custom_profile_fields_to_settings();
            break;

        case "default_streams":
            stream_data.set_realm_default_streams(event.default_streams);
            settings_streams.update_default_streams_table();
            break;

        case "delete_message": {
            const msg_ids = event.message_ids;
            // message is passed to unread.get_unread_messages,
            // which returns all the unread messages out of a given list.
            // So double marking something as read would not occur
            unread_ops.process_read_messages_event(msg_ids);
            // This methods updates message_list too and since stream_topic_history relies on it
            // this method should be called first.
            ui.remove_messages(msg_ids);

            if (event.message_type === "stream") {
                stream_topic_history.remove_messages({
                    stream_id: event.stream_id,
                    topic_name: event.topic,
                    num_messages: msg_ids.length,
                    max_removed_msg_id: Math.max(...msg_ids),
                });
                stream_list.update_streams_sidebar();
            }

            break;
        }

        case "has_zoom_token":
            page_params.has_zoom_token = event.value;
            if (event.value) {
                for (const callback of compose.zoom_token_callbacks.values()) {
                    callback();
                }
                compose.zoom_token_callbacks.clear();
            }
            break;

        case "hotspots":
            hotspots.load_new(event.hotspots);
            page_params.hotspots = page_params.hotspots
                ? page_params.hotspots.concat(event.hotspots)
                : event.hotspots;
            break;

        case "invites_changed":
            if ($("#admin-invites-list").length) {
                settings_invites.set_up(false);
            }
            break;

        case "muted_topics":
            muting_ui.handle_updates(event.muted_topics);
            break;

        case "presence":
            activity.update_presence_info(event.user_id, event.presence, event.server_timestamp);
            break;

        case "restart": {
            const reload_options = {
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
        }

        case "reaction":
            if (event.op === "add") {
                reactions.add_reaction(event);
            } else if (event.op === "remove") {
                reactions.remove_reaction(event);
            }
            break;

        case "realm": {
            const realm_settings = {
                add_emoji_by_admins_only: settings_emoji.update_custom_emoji_ui,
                allow_edit_history: noop,
                allow_message_deleting: noop,
                allow_message_editing: noop,
                allow_community_topic_editing: noop,
                user_group_edit_policy: noop,
                avatar_changes_disabled: settings_account.update_avatar_change_display,
                bot_creation_policy: settings_bots.update_bot_permissions_ui,
                create_stream_policy: noop,
                invite_to_stream_policy: noop,
                default_code_block_language: noop,
                default_language: noop,
                default_twenty_four_hour_time: noop,
                description: noop,
                digest_emails_enabled: noop,
                digest_weekday: noop,
                email_address_visibility: noop,
                email_changes_disabled: settings_account.update_email_change_display,
                disallow_disposable_email_addresses: noop,
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
                private_message_policy: noop,
                send_welcome_emails: noop,
                message_content_allowed_in_email_notifications: noop,
                signup_notifications_stream_id: noop,
                emails_restricted_to_domains: noop,
                video_chat_provider: compose.update_video_chat_button_display,
                waiting_period_threshold: noop,
            };
            if (
                event.op === "update" &&
                Object.prototype.hasOwnProperty.call(realm_settings, event.property)
            ) {
                page_params["realm_" + event.property] = event.value;
                realm_settings[event.property]();
                settings_org.sync_realm_settings(event.property);
                if (event.property === "create_stream_policy") {
                    // TODO: Add waiting_period_threshold logic here.
                    page_params.can_create_streams =
                        page_params.is_admin || page_params.realm_create_stream_policy === 1;
                } else if (event.property === "invite_to_stream_policy") {
                    // TODO: Add waiting_period_threshold logic here.
                    page_params.can_invite_to_stream =
                        page_params.is_admin || page_params.realm_invite_to_stream_policy === 1;
                }

                if (event.property === "name" && window.electron_bridge !== undefined) {
                    window.electron_bridge.send_event("realm_name", event.value);
                }
            } else if (event.op === "update_dict" && event.property === "default") {
                for (const [key, value] of Object.entries(event.data)) {
                    page_params["realm_" + key] = value;
                    if (key === "allow_message_editing") {
                        message_edit.update_message_topic_editing_pencil();
                    }
                    if (Object.prototype.hasOwnProperty.call(realm_settings, key)) {
                        settings_org.sync_realm_settings(key);
                    }
                }
                if (event.data.authentication_methods !== undefined) {
                    settings_org.populate_auth_methods(event.data.authentication_methods);
                }
            } else if (event.op === "update_dict" && event.property === "icon") {
                page_params.realm_icon_url = event.data.icon_url;
                page_params.realm_icon_source = event.data.icon_source;
                realm_icon.rerender();

                const electron_bridge = window.electron_bridge;
                if (electron_bridge !== undefined) {
                    electron_bridge.send_event("realm_icon_url", event.data.icon_url);
                }
            } else if (event.op === "update_dict" && event.property === "logo") {
                page_params.realm_logo_url = event.data.logo_url;
                page_params.realm_logo_source = event.data.logo_source;
                realm_logo.rerender();
            } else if (event.op === "update_dict" && event.property === "night_logo") {
                page_params.realm_night_logo_url = event.data.night_logo_url;
                page_params.realm_night_logo_source = event.data.night_logo_source;
                realm_logo.rerender();
            } else if (event.op === "deactivated") {
                window.location.href = "/accounts/deactivated/";
            }

            if (page_params.is_admin) {
                // Update the UI notice about the user's profile being
                // incomplete, as we might have filled in the missing field(s).
                panels.check_profile_incomplete();
            }
            break;
        }

        case "realm_bot":
            if (event.op === "add") {
                bot_data.add(event.bot);
            } else if (event.op === "remove") {
                bot_data.deactivate(event.bot.user_id);
                event.bot.is_active = false;
            } else if (event.op === "delete") {
                blueslip.info("ignoring bot deletion for live UI update");
                break;
            } else if (event.op === "update") {
                bot_data.update(event.bot.user_id, event.bot);
            }
            settings_users.update_bot_data(event.bot.user_id);
            break;

        case "realm_emoji":
            // The authoritative data source is here.
            emoji.update_emojis(event.realm_emoji);

            // And then let other widgets know.
            settings_emoji.populate_emoji();
            emoji_picker.rebuild_catalog();
            composebox_typeahead.update_emoji_data();
            break;

        case "realm_filters":
            page_params.realm_filters = event.realm_filters;
            markdown.update_realm_filter_rules(page_params.realm_filters);
            settings_linkifiers.populate_filters(page_params.realm_filters);
            break;

        case "realm_domains": {
            let i;
            if (event.op === "add") {
                page_params.realm_domains.push(event.realm_domain);
            } else if (event.op === "change") {
                for (i = 0; i < page_params.realm_domains.length; i += 1) {
                    if (page_params.realm_domains[i].domain === event.realm_domain.domain) {
                        page_params.realm_domains[i].allow_subdomains =
                            event.realm_domain.allow_subdomains;
                        break;
                    }
                }
            } else if (event.op === "remove") {
                for (i = 0; i < page_params.realm_domains.length; i += 1) {
                    if (page_params.realm_domains[i].domain === event.domain) {
                        page_params.realm_domains.splice(i, 1);
                        break;
                    }
                }
            }
            settings_org.populate_realm_domains(page_params.realm_domains);
            break;
        }

        case "realm_user":
            if (event.op === "add") {
                people.add_active_user(event.person);
            } else if (event.op === "remove") {
                people.deactivate(event.person);
                stream_events.remove_deactivated_user_from_all_streams(event.person.user_id);
            } else if (event.op === "update") {
                user_events.update_person(event.person);
            }
            break;

        case "stream":
            if (event.op === "update") {
                // Legacy: Stream properties are still managed by subs.js on the client side.
                stream_events.update_property(event.stream_id, event.property, event.value, {
                    rendered_description: event.rendered_description,
                    history_public_to_subscribers: event.history_public_to_subscribers,
                });
                settings_streams.update_default_streams_table();
            } else if (event.op === "create") {
                stream_data.create_streams(event.streams);

                for (const stream of event.streams) {
                    const sub = stream_data.get_sub_by_id(stream.stream_id);
                    stream_data.update_calculated_fields(sub);
                    if (overlays.streams_open()) {
                        subs.add_sub_to_table(sub);
                    }
                }
            } else if (event.op === "delete") {
                for (const stream of event.streams) {
                    const was_subscribed = stream_data.get_sub_by_id(stream.stream_id).subscribed;
                    const is_narrowed_to_stream = narrow_state.is_for_stream_id(stream.stream_id);
                    subs.remove_stream(stream.stream_id);
                    stream_data.delete_sub(stream.stream_id);
                    if (was_subscribed) {
                        stream_list.remove_sidebar_row(stream.stream_id);
                    }
                    settings_streams.update_default_streams_table();
                    stream_data.remove_default_stream(stream.stream_id);
                    if (is_narrowed_to_stream) {
                        current_msg_list.update_trailing_bookend();
                    }
                    if (page_params.realm_notifications_stream_id === stream.stream_id) {
                        page_params.realm_notifications_stream_id = -1;
                        settings_org.sync_realm_settings("notifications_stream_id");
                    }
                    if (page_params.realm_signup_notifications_stream_id === stream.stream_id) {
                        page_params.realm_signup_notifications_stream_id = -1;
                        settings_org.sync_realm_settings("signup_notifications_stream_id");
                    }
                }
            }
            break;

        case "submessage": {
            // The fields in the event don't quite exactly
            // match the layout of a submessage, since there's
            // an event id.  We also want to be explicit here.
            const submsg = {
                id: event.submessage_id,
                sender_id: event.sender_id,
                msg_type: event.msg_type,
                message_id: event.message_id,
                content: event.content,
            };
            submessage.handle_event(submsg);
            break;
        }

        case "subscription":
            if (event.op === "add") {
                for (const rec of event.subscriptions) {
                    const sub = stream_data.get_sub_by_id(rec.stream_id);
                    if (sub) {
                        stream_data.update_stream_email_address(sub, rec.email_address);
                        stream_events.mark_subscribed(sub, rec.subscribers, rec.color);
                    } else {
                        blueslip.error("Subscribing to unknown stream with ID " + rec.stream_id);
                    }
                }
            } else if (event.op === "peer_add") {
                function add_peer(stream_id, user_id) {
                    const sub = stream_data.get_sub_by_id(stream_id);

                    if (!sub) {
                        blueslip.warn("Cannot find stream for peer_add: " + stream_id);
                        return;
                    }

                    if (!stream_data.add_subscriber(stream_id, user_id)) {
                        blueslip.warn("Cannot process peer_add event");
                        return;
                    }

                    subs.update_subscribers_ui(sub);
                    compose_fade.update_faded_users();
                }
                add_peer(event.stream_id, event.user_id);
            } else if (event.op === "peer_remove") {
                function remove_peer(stream_id, user_id) {
                    const sub = stream_data.get_sub_by_id(stream_id);

                    if (!sub) {
                        blueslip.warn("Cannot find stream for peer_remove: " + stream_id);
                        return;
                    }

                    if (!stream_data.remove_subscriber(sub.stream_id, user_id)) {
                        blueslip.warn("Cannot process peer_remove event.");
                        return;
                    }

                    subs.update_subscribers_ui(sub);
                    compose_fade.update_faded_users();
                }
                remove_peer(event.stream_id, event.user_id);
            } else if (event.op === "remove") {
                for (const rec of event.subscriptions) {
                    const sub = stream_data.get_sub_by_id(rec.stream_id);
                    stream_events.mark_unsubscribed(sub);
                }
            } else if (event.op === "update") {
                stream_events.update_property(event.stream_id, event.property, event.value);
            }
            break;

        case "typing":
            if (event.sender.user_id === page_params.user_id) {
                // typing notifications are sent to the user who is typing
                // as well as recipients; we ignore such self-generated events.
                return;
            }

            if (event.op === "start") {
                typing_events.display_notification(event);
            } else if (event.op === "stop") {
                typing_events.hide_notification(event);
            }
            break;

        case "update_display_settings": {
            const user_display_settings = [
                "color_scheme",
                "default_language",
                "demote_inactive_streams",
                "dense_mode",
                "emojiset",
                "fluid_layout_width",
                "high_contrast_mode",
                "left_side_userlist",
                "timezone",
                "twenty_four_hour_time",
                "translate_emoticons",
                "starred_message_counts",
            ];
            if (user_display_settings.includes(event.setting_name)) {
                page_params[event.setting_name] = event.setting;
            }
            if (event.setting_name === "default_language") {
                // We additionally need to set the language name.
                page_params.default_language_name = event.language_name;
            }
            if (event.setting_name === "twenty_four_hour_time") {
                // Rerender the whole message list UI
                home_msg_list.rerender();
                if (current_msg_list === message_list.narrowed) {
                    message_list.narrowed.rerender();
                }
            }
            if (event.setting_name === "high_contrast_mode") {
                $("body").toggleClass("high-contrast");
            }
            if (event.setting_name === "demote_inactive_streams") {
                stream_list.update_streams_sidebar();
                stream_data.set_filter_out_inactives();
            }
            if (event.setting_name === "dense_mode") {
                $("body").toggleClass("less_dense_mode");
                $("body").toggleClass("more_dense_mode");
            }
            if (event.setting_name === "color_scheme") {
                $("body").fadeOut(300);
                setTimeout(() => {
                    if (event.setting === settings_config.color_scheme_values.night.code) {
                        night_mode.enable();
                        realm_logo.rerender();
                    } else if (event.setting === settings_config.color_scheme_values.day.code) {
                        night_mode.disable();
                        realm_logo.rerender();
                    } else {
                        night_mode.default_preference_checker();
                        realm_logo.rerender();
                    }
                    $("body").fadeIn(300);
                }, 300);
            }
            if (event.setting_name === "starred_message_counts") {
                starred_messages.rerender_ui();
            }
            if (event.setting_name === "fluid_layout_width") {
                scroll_bar.set_layout_width();
            }
            if (event.setting_name === "left_side_userlist") {
                // TODO: Make this change the view immediately rather
                // than requiring a reload or page resize.
            }
            if (event.setting_name === "default_language") {
                // TODO: Make this change the view immediately rather than
                // requiring a reload.  This is likely fairly difficult,
                // because various i18n strings are rendered by the
                // server; we may want to instead just trigger a page
                // reload.
            }
            if (event.setting_name === "emojiset") {
                settings_display.report_emojiset_change();

                // Rerender the whole message list UI
                home_msg_list.rerender();
                if (current_msg_list === message_list.narrowed) {
                    message_list.narrowed.rerender();
                }
            }
            settings_display.update_page();
            break;
        }

        case "update_global_notifications":
            notifications.handle_global_notification_updates(
                event.notification_name,
                event.setting,
            );
            settings_notifications.update_page();
            // TODO: This should also do a refresh of the stream_edit UI
            // if it's currently displayed, possibly reusing some code
            // from stream_events.js
            // (E.g. update_stream_push_notifications).
            break;

        case "update_message_flags": {
            const new_value = event.op === "add";
            switch (event.flag) {
                case "starred":
                    for (const message_id of event.messages) {
                        message_flags.update_starred_flag(message_id, new_value);
                    }

                    if (event.op === "add") {
                        starred_messages.add(event.messages);
                    } else {
                        starred_messages.remove(event.messages);
                    }
                    break;
                case "read":
                    unread_ops.process_read_messages_event(event.messages);
                    break;
            }
            break;
        }

        case "user_group":
            if (event.op === "add") {
                user_groups.add(event.group);
            } else if (event.op === "add_members") {
                user_groups.add_members(event.group_id, event.user_ids);
            } else if (event.op === "remove_members") {
                user_groups.remove_members(event.group_id, event.user_ids);
            } else if (event.op === "update") {
                user_groups.update(event);
            }
            settings_user_groups.reload();
            break;

        case "user_status":
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
        case "realm_export":
            settings_exports.populate_exports_table(event.exports);
            break;
    }
};

window.server_events_dispatch = exports;
