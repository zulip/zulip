import $ from "jquery";
import assert from "minimalistic-assert";

import * as activity_ui from "./activity_ui";
import * as alert_words from "./alert_words";
import * as alert_words_ui from "./alert_words_ui";
import * as attachments_ui from "./attachments_ui";
import * as audible_notifications from "./audible_notifications";
import * as blueslip from "./blueslip";
import * as bot_data from "./bot_data";
import * as browser_history from "./browser_history";
import {buddy_list} from "./buddy_list";
import * as compose_call from "./compose_call";
import * as compose_call_ui from "./compose_call_ui";
import * as compose_pm_pill from "./compose_pm_pill";
import * as compose_recipient from "./compose_recipient";
import * as compose_state from "./compose_state";
import * as dark_theme from "./dark_theme";
import * as emoji from "./emoji";
import * as emoji_picker from "./emoji_picker";
import * as gear_menu from "./gear_menu";
import * as giphy from "./giphy";
import * as hotspots from "./hotspots";
import * as information_density from "./information_density";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area";
import * as linkifiers from "./linkifiers";
import * as message_edit from "./message_edit";
import * as message_events from "./message_events";
import * as message_lists from "./message_lists";
import * as message_live_update from "./message_live_update";
import * as muted_users_ui from "./muted_users_ui";
import * as narrow_state from "./narrow_state";
import * as narrow_title from "./narrow_title";
import * as navbar_alerts from "./navbar_alerts";
import * as onboarding_steps from "./onboarding_steps";
import * as overlays from "./overlays";
import * as peer_data from "./peer_data";
import * as people from "./people";
import * as pm_list from "./pm_list";
import * as reactions from "./reactions";
import * as realm_icon from "./realm_icon";
import * as realm_logo from "./realm_logo";
import * as realm_playground from "./realm_playground";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults";
import * as reload from "./reload";
import * as scheduled_messages from "./scheduled_messages";
import * as scheduled_messages_feed_ui from "./scheduled_messages_feed_ui";
import * as scheduled_messages_overlay_ui from "./scheduled_messages_overlay_ui";
import * as scheduled_messages_ui from "./scheduled_messages_ui";
import * as scroll_bar from "./scroll_bar";
import * as settings_account from "./settings_account";
import * as settings_bots from "./settings_bots";
import * as settings_components from "./settings_components";
import * as settings_config from "./settings_config";
import * as settings_emoji from "./settings_emoji";
import * as settings_exports from "./settings_exports";
import * as settings_invites from "./settings_invites";
import * as settings_linkifiers from "./settings_linkifiers";
import * as settings_notifications from "./settings_notifications";
import * as settings_org from "./settings_org";
import * as settings_playgrounds from "./settings_playgrounds";
import * as settings_preferences from "./settings_preferences";
import * as settings_profile_fields from "./settings_profile_fields";
import * as settings_realm_domains from "./settings_realm_domains";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults";
import * as settings_streams from "./settings_streams";
import * as settings_users from "./settings_users";
import * as sidebar_ui from "./sidebar_ui";
import * as starred_messages from "./starred_messages";
import * as starred_messages_ui from "./starred_messages_ui";
import {current_user, realm} from "./state_data";
import * as stream_data from "./stream_data";
import * as stream_events from "./stream_events";
import * as stream_list from "./stream_list";
import * as stream_list_sort from "./stream_list_sort";
import * as stream_settings_ui from "./stream_settings_ui";
import * as stream_topic_history from "./stream_topic_history";
import * as stream_ui_updates from "./stream_ui_updates";
import * as sub_store from "./sub_store";
import * as submessage from "./submessage";
import * as typing_events from "./typing_events";
import * as unread_ops from "./unread_ops";
import * as unread_ui from "./unread_ui";
import * as user_events from "./user_events";
import * as user_group_edit from "./user_group_edit";
import * as user_groups from "./user_groups";
import {user_settings} from "./user_settings";
import * as user_status from "./user_status";
import * as user_topics_ui from "./user_topics_ui";

export function dispatch_normal_event(event) {
    const noop = function () {};
    switch (event.type) {
        case "alert_words":
            alert_words.set_words(event.alert_words);
            alert_words_ui.rerender_alert_words_ui();
            break;

        case "attachment":
            attachments_ui.update_attachments(event);
            break;

        case "custom_profile_fields":
            realm.custom_profile_fields = event.fields;
            settings_profile_fields.populate_profile_fields(realm.custom_profile_fields);
            settings_account.add_custom_profile_fields_to_settings();
            navbar_alerts.maybe_show_empty_required_profile_fields_alert();
            break;

        case "default_streams":
            stream_data.set_realm_default_streams(event.default_streams);
            settings_streams.update_default_streams_table();
            stream_settings_ui.update_is_default_stream();
            break;

        case "delete_message": {
            const msg_ids = event.message_ids;
            // message is passed to unread.get_unread_messages,
            // which returns all the unread messages out of a given list.
            // So double marking something as read would not occur
            unread_ops.process_read_messages_event(msg_ids);
            // This methods updates message_list too and since stream_topic_history relies on it
            // this method should be called first.
            message_events.remove_messages(msg_ids);

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
            current_user.has_zoom_token = event.value;
            if (event.value) {
                for (const callback of compose_call.zoom_token_callbacks.values()) {
                    callback();
                }
                compose_call.zoom_token_callbacks.clear();
            }
            break;

        case "onboarding_steps":
            hotspots.load_new(onboarding_steps.filter_new_hotspots(event.onboarding_steps));
            onboarding_steps.update_notice_to_display(event.onboarding_steps);
            current_user.onboarding_steps = current_user.onboarding_steps
                ? [...current_user.onboarding_steps, ...event.onboarding_steps]
                : event.onboarding_steps;
            break;

        case "invites_changed":
            if ($("#admin-invites-list").length) {
                settings_invites.set_up(false);
            }
            break;

        case "muted_users":
            muted_users_ui.handle_user_updates(event.muted_users);
            break;

        case "presence":
            activity_ui.update_presence_info(event.user_id, event.presence, event.server_timestamp);
            break;

        case "restart":
            realm.zulip_version = event.zulip_version;
            realm.zulip_merge_base = event.zulip_merge_base;
            break;

        case "web_reload_client": {
            const reload_options = {
                save_compose: true,
                message_html: "The application has been updated; reloading!",
            };
            if (event.immediate) {
                reload_options.immediate = true;
            }
            reload.initiate(reload_options);
            break;
        }

        case "reaction":
            switch (event.op) {
                case "add":
                    reactions.add_reaction(event);
                    break;
                case "remove":
                    reactions.remove_reaction(event);
                    break;
                default:
                    blueslip.error("Unexpected event type reaction/" + event.op);
                    break;
            }
            break;

        case "realm": {
            const realm_settings = {
                add_custom_emoji_policy: settings_emoji.update_custom_emoji_ui,
                allow_edit_history: noop,
                allow_message_editing: noop,
                edit_topic_policy: noop,
                user_group_edit_policy: noop,
                avatar_changes_disabled: settings_account.update_avatar_change_display,
                bot_creation_policy: settings_bots.update_bot_permissions_ui,
                create_multiuse_invite_group: noop,
                create_public_stream_policy: noop,
                create_private_stream_policy: noop,
                create_web_public_stream_policy: noop,
                invite_to_stream_policy: noop,
                default_code_block_language: noop,
                default_language: noop,
                delete_own_message_policy: noop,
                description: noop,
                digest_emails_enabled: noop,
                digest_weekday: noop,
                email_changes_disabled: settings_account.update_email_change_display,
                disallow_disposable_email_addresses: noop,
                inline_image_preview: noop,
                inline_url_embed_preview: noop,
                invite_to_realm_policy: noop,
                invite_required: noop,
                mandatory_topics: noop,
                message_content_edit_limit_seconds: noop,
                message_content_delete_limit_seconds: noop,
                move_messages_between_streams_limit_seconds: noop,
                move_messages_within_stream_limit_seconds: message_edit.update_inline_topic_edit_ui,
                message_retention_days: noop,
                move_messages_between_streams_policy: noop,
                name: narrow_title.redraw_title,
                name_changes_disabled: settings_account.update_name_change_display,
                new_stream_announcements_stream_id: stream_ui_updates.update_announce_stream_option,
                org_type: noop,
                private_message_policy: compose_recipient.check_posting_policy_for_compose_box,
                push_notifications_enabled: noop,
                require_unique_names: noop,
                send_welcome_emails: noop,
                message_content_allowed_in_email_notifications: noop,
                enable_spectator_access: noop,
                signup_announcements_stream_id: noop,
                zulip_update_announcements_stream_id: noop,
                emails_restricted_to_domains: noop,
                video_chat_provider: compose_call_ui.update_audio_and_video_chat_button_display,
                jitsi_server_url: compose_call_ui.update_audio_and_video_chat_button_display,
                giphy_rating: giphy.update_giphy_rating,
                waiting_period_threshold: noop,
                want_advertise_in_communities_directory: noop,
                wildcard_mention_policy: noop,
                enable_read_receipts: settings_account.update_send_read_receipts_tooltip,
                enable_guest_user_indicator: noop,
            };
            switch (event.op) {
                case "update":
                    if (Object.hasOwn(realm_settings, event.property)) {
                        realm["realm_" + event.property] = event.value;
                        realm_settings[event.property]();
                        settings_org.sync_realm_settings(event.property);

                        if (event.property === "name" && window.electron_bridge !== undefined) {
                            window.electron_bridge.send_event("realm_name", event.value);
                        }

                        if (event.property === "invite_to_realm_policy") {
                            settings_invites.update_invite_user_panel();
                            sidebar_ui.update_invite_user_option();
                            gear_menu.rerender();
                        }

                        const stream_creation_settings = [
                            "create_private_stream_policy",
                            "create_public_stream_policy",
                            "create_web_public_stream_policy",
                        ];
                        if (stream_creation_settings.includes(event.property)) {
                            stream_settings_ui.update_stream_privacy_choices(event.property);
                        }

                        if (event.property === "enable_spectator_access") {
                            stream_settings_ui.update_stream_privacy_choices(
                                "create_web_public_stream_policy",
                            );
                        }
                    }
                    break;
                case "update_dict":
                    switch (event.property) {
                        case "default":
                            for (const [key, value] of Object.entries(event.data)) {
                                realm["realm_" + key] = value;
                                if (Object.hasOwn(realm_settings, key)) {
                                    settings_org.sync_realm_settings(key);
                                }

                                if (key === "create_multiuse_invite_group") {
                                    settings_invites.update_invite_user_panel();
                                    sidebar_ui.update_invite_user_option();
                                    gear_menu.rerender();
                                }

                                if (key === "edit_topic_policy") {
                                    message_live_update.rerender_messages_view();
                                }
                            }
                            if (event.data.authentication_methods !== undefined) {
                                settings_org.populate_auth_methods(
                                    settings_components.realm_authentication_methods_to_boolean_dict(),
                                );
                            }
                            break;
                        case "icon":
                            realm.realm_icon_url = event.data.icon_url;
                            realm.realm_icon_source = event.data.icon_source;
                            realm_icon.rerender();
                            {
                                const electron_bridge = window.electron_bridge;
                                if (electron_bridge !== undefined) {
                                    electron_bridge.send_event(
                                        "realm_icon_url",
                                        event.data.icon_url,
                                    );
                                }
                            }
                            break;
                        case "logo":
                            realm.realm_logo_url = event.data.logo_url;
                            realm.realm_logo_source = event.data.logo_source;
                            realm_logo.render();
                            break;
                        case "night_logo":
                            realm.realm_night_logo_url = event.data.night_logo_url;
                            realm.realm_night_logo_source = event.data.night_logo_source;
                            realm_logo.render();
                            break;
                        default:
                            blueslip.error(
                                "Unexpected event type realm/update_dict/" + event.property,
                            );
                            break;
                    }
                    break;
                case "deactivated":
                    // This handler is likely unnecessary, in that if we
                    // did nothing here, we'd reload and end up at the
                    // same place when we attempt the next `GET /events`
                    // and get an error.  Some clients will do that even
                    // with this code, if they didn't have an active
                    // longpoll waiting at the moment the realm was
                    // deactivated.
                    window.location.href = "/accounts/deactivated/";
                    break;
            }
            if (current_user.is_admin) {
                // Update the UI notice about the user's profile being
                // incomplete, as we might have filled in the missing field(s).
                navbar_alerts.show_profile_incomplete(navbar_alerts.check_profile_incomplete());
            }
            break;
        }

        case "realm_bot":
            switch (event.op) {
                case "add":
                    bot_data.add(event.bot);
                    settings_bots.render_bots();
                    break;
                case "delete":
                    bot_data.del(event.bot.user_id);
                    settings_bots.render_bots();
                    break;
                case "update":
                    bot_data.update(event.bot.user_id, event.bot);
                    settings_bots.render_bots();
                    break;
                default:
                    blueslip.error("Unexpected event type realm_bot/" + event.op);
                    break;
            }
            break;

        case "realm_emoji":
            // The authoritative data source is here.
            emoji.update_emojis(event.realm_emoji);

            // And then let other widgets know.
            settings_emoji.populate_emoji();
            emoji_picker.rebuild_catalog();
            break;

        case "realm_export":
            settings_exports.populate_exports_table(event.exports);
            break;

        case "realm_linkifiers":
            realm.realm_linkifiers = event.realm_linkifiers;
            linkifiers.update_linkifier_rules(realm.realm_linkifiers);
            settings_linkifiers.populate_linkifiers(realm.realm_linkifiers);
            break;

        case "realm_playgrounds":
            realm.realm_playgrounds = event.realm_playgrounds;
            realm_playground.update_playgrounds(realm.realm_playgrounds);
            settings_playgrounds.populate_playgrounds(realm.realm_playgrounds);
            break;

        case "realm_domains":
            {
                let i;
                switch (event.op) {
                    case "add":
                        realm.realm_domains.push(event.realm_domain);
                        settings_org.populate_realm_domains_label(realm.realm_domains);
                        settings_realm_domains.populate_realm_domains_table(realm.realm_domains);
                        break;
                    case "change":
                        for (i = 0; i < realm.realm_domains.length; i += 1) {
                            if (realm.realm_domains[i].domain === event.realm_domain.domain) {
                                realm.realm_domains[i].allow_subdomains =
                                    event.realm_domain.allow_subdomains;
                                break;
                            }
                        }
                        settings_org.populate_realm_domains_label(realm.realm_domains);
                        settings_realm_domains.populate_realm_domains_table(realm.realm_domains);
                        break;
                    case "remove":
                        for (i = 0; i < realm.realm_domains.length; i += 1) {
                            if (realm.realm_domains[i].domain === event.domain) {
                                realm.realm_domains.splice(i, 1);
                                break;
                            }
                        }
                        settings_org.populate_realm_domains_label(realm.realm_domains);
                        settings_realm_domains.populate_realm_domains_table(realm.realm_domains);
                        break;
                    default:
                        blueslip.error("Unexpected event type realm_domains/" + event.op);
                        break;
                }
            }
            break;

        case "realm_user_settings_defaults": {
            realm_user_settings_defaults[event.property] = event.value;
            settings_realm_user_settings_defaults.update_page(event.property);

            if (event.property === "notification_sound") {
                audible_notifications.update_notification_sound_source(
                    $("audio#realm-default-notification-sound-audio"),
                    realm_user_settings_defaults,
                );
            }
            break;
        }

        case "realm_user":
            switch (event.op) {
                case "add":
                    people.add_active_user(event.person);
                    settings_account.maybe_update_deactivate_account_button();
                    if (event.person.is_bot) {
                        settings_users.redraw_bots_list();
                    }
                    break;
                case "update":
                    user_events.update_person(event.person);
                    settings_account.maybe_update_deactivate_account_button();
                    if (people.is_valid_bot_user(event.person.user_id)) {
                        settings_users.update_bot_data(event.person.user_id);
                    }
                    break;
                case "remove": {
                    const user_id = event.person.user_id;
                    people.remove_inaccessible_user(user_id);
                    buddy_list.maybe_remove_user_id({user_id});
                    message_live_update.update_user_full_name(
                        user_id,
                        people.INACCESSIBLE_USER_NAME,
                    );
                    break;
                }
                default:
                    blueslip.error("Unexpected event type realm_user/" + event.op);
                    break;
            }
            break;

        case "scheduled_messages":
            switch (event.op) {
                case "add": {
                    scheduled_messages.add_scheduled_messages(event.scheduled_messages);
                    scheduled_messages_feed_ui.update_schedule_message_indicator();
                    scheduled_messages_overlay_ui.rerender();
                    left_sidebar_navigation_area.update_scheduled_messages_row();
                    break;
                }
                case "remove": {
                    scheduled_messages.remove_scheduled_message(event.scheduled_message_id);
                    scheduled_messages_feed_ui.update_schedule_message_indicator();
                    scheduled_messages_ui.hide_scheduled_message_success_compose_banner(
                        event.scheduled_message_id,
                    );
                    scheduled_messages_overlay_ui.remove_scheduled_message_id(
                        event.scheduled_message_id,
                    );
                    left_sidebar_navigation_area.update_scheduled_messages_row();
                    break;
                }
                case "update": {
                    scheduled_messages.update_scheduled_message(event.scheduled_message);
                    scheduled_messages_overlay_ui.rerender();
                    left_sidebar_navigation_area.update_scheduled_messages_row();
                    break;
                }
                // No default
            }
            break;

        case "stream":
            switch (event.op) {
                case "update":
                    stream_events.update_property(event.stream_id, event.property, event.value, {
                        rendered_description: event.rendered_description,
                        history_public_to_subscribers: event.history_public_to_subscribers,
                        is_web_public: event.is_web_public,
                    });
                    settings_streams.update_default_streams_table();
                    stream_list.update_subscribe_to_more_streams_link();
                    break;
                case "create":
                    stream_data.create_streams(event.streams);

                    for (const stream of event.streams) {
                        const sub = sub_store.get(stream.stream_id);
                        if (overlays.streams_open()) {
                            stream_settings_ui.add_sub_to_table(sub);
                        }
                    }
                    stream_list.update_subscribe_to_more_streams_link();
                    break;
                case "delete":
                    for (const stream of event.streams) {
                        const was_subscribed = sub_store.get(stream.stream_id).subscribed;
                        const is_narrowed_to_stream = narrow_state.is_for_stream_id(
                            stream.stream_id,
                        );
                        if (is_narrowed_to_stream) {
                            assert(message_lists.current !== undefined);
                            message_lists.current.update_trailing_bookend();
                        }
                        stream_data.delete_sub(stream.stream_id);
                        stream_settings_ui.remove_stream(stream.stream_id);
                        if (was_subscribed) {
                            stream_list.remove_sidebar_row(stream.stream_id);
                            if (stream.stream_id === compose_state.selected_recipient_id) {
                                compose_state.set_selected_recipient_id("");
                                compose_recipient.on_compose_select_recipient_update();
                            }
                        }
                        settings_streams.update_default_streams_table();
                        stream_data.remove_default_stream(stream.stream_id);
                        if (realm.realm_new_stream_announcements_stream_id === stream.stream_id) {
                            realm.realm_new_stream_announcements_stream_id = -1;
                            settings_org.sync_realm_settings("new_stream_announcements_stream_id");
                        }
                        if (realm.realm_signup_announcements_stream_id === stream.stream_id) {
                            realm.realm_signup_announcements_stream_id = -1;
                            settings_org.sync_realm_settings("signup_announcements_stream_id");
                        }
                        if (realm.realm_zulip_update_announcements_stream_id === stream.stream_id) {
                            realm.realm_zulip_update_announcements_stream_id = -1;
                            settings_org.sync_realm_settings(
                                "zulip_update_announcements_stream_id",
                            );
                        }
                    }
                    stream_list.update_subscribe_to_more_streams_link();
                    break;
                default:
                    blueslip.error("Unexpected event type stream/" + event.op);
                    break;
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
            switch (event.op) {
                case "add":
                    for (const rec of event.subscriptions) {
                        const sub = sub_store.get(rec.stream_id);
                        if (sub) {
                            stream_data.update_stream_email_address(sub, rec.email_address);
                            stream_events.mark_subscribed(sub, rec.subscribers, rec.color);
                        } else {
                            blueslip.error("Subscribing to unknown stream", {
                                stream_id: rec.stream_id,
                            });
                        }
                    }
                    break;
                case "peer_add": {
                    const stream_ids = sub_store.validate_stream_ids(event.stream_ids);
                    const user_ids = people.validate_user_ids(event.user_ids);

                    peer_data.bulk_add_subscribers({stream_ids, user_ids});
                    stream_events.process_subscriber_update(user_ids, stream_ids);
                    break;
                }
                case "peer_remove": {
                    const stream_ids = sub_store.validate_stream_ids(event.stream_ids);
                    const user_ids = people.validate_user_ids(event.user_ids);

                    peer_data.bulk_remove_subscribers({stream_ids, user_ids});
                    stream_events.process_subscriber_update(user_ids, stream_ids);
                    break;
                }
                case "remove":
                    for (const rec of event.subscriptions) {
                        const sub = sub_store.get(rec.stream_id);
                        stream_events.mark_unsubscribed(sub);
                    }
                    break;
                case "update":
                    stream_events.update_property(event.stream_id, event.property, event.value);
                    break;
                default:
                    blueslip.error("Unexpected event type subscription/" + event.op);
                    break;
            }
            break;
        case "typing":
            if (event.sender.user_id === current_user.user_id) {
                // typing notifications are sent to the user who is typing
                // as well as recipients; we ignore such self-generated events.
                return;
            }
            switch (event.op) {
                case "start":
                    typing_events.display_notification(event);
                    break;
                case "stop":
                    typing_events.hide_notification(event);
                    break;
                default:
                    blueslip.error("Unexpected event type typing/" + event.op);
                    break;
            }
            break;

        case "user_settings": {
            const notification_name = event.property;
            if (settings_config.all_notification_settings.includes(notification_name)) {
                // Update the global settings checked when determining if we should notify
                // for a given message. These settings do not affect whether or not a
                // particular stream should receive notifications.
                user_settings[notification_name] = event.value;

                if (settings_config.stream_notification_settings.includes(notification_name)) {
                    stream_ui_updates.update_notification_setting_checkbox(
                        settings_config.specialize_stream_notification_setting[notification_name],
                    );
                }

                if (notification_name === "notification_sound") {
                    // Change the sound source with the new page `notification_sound`.
                    audible_notifications.update_notification_sound_source(
                        $("audio#user-notification-sound-audio"),
                        user_settings,
                    );
                }
                settings_notifications.update_page(settings_notifications.user_settings_panel);
                break;
            }

            const user_display_settings = [
                "color_scheme",
                "web_font_size_px",
                "web_line_height_percent",
                "default_language",
                "web_home_view",
                "demote_inactive_streams",
                "dense_mode",
                "web_mark_read_on_scroll_policy",
                "emojiset",
                "web_escape_navigates_to_home_view",
                "fluid_layout_width",
                "high_contrast_mode",
                "receives_typing_notifications",
                "timezone",
                "twenty_four_hour_time",
                "translate_emoticons",
                "display_emoji_reaction_users",
                "user_list_style",
                "web_stream_unreads_count_display_policy",
                "starred_message_counts",
                "send_stream_typing_notifications",
                "send_private_typing_notifications",
                "send_read_receipts",
            ];

            const original_home_view = user_settings.web_home_view;
            if (user_display_settings.includes(event.property)) {
                user_settings[event.property] = event.value;
            }
            if (event.property === "default_language") {
                // We additionally need to set the language name.
                //
                // Note that this does not change translations at all;
                // a reload is fundamentally required because we
                // cannot rerender with the new language the strings
                // present in the backend/Jinja2 templates.
                settings_preferences.set_default_language_name(event.language_name);
            }
            if (event.property === "web_home_view") {
                left_sidebar_navigation_area.handle_home_view_changed(event.value);

                // If current hash is empty (home view), and the
                // user changes the home view while in settings,
                // then going back to an empty hash on closing the
                // overlay will not match the view currently displayed
                // under settings, so we set the hash to the previous
                // value of the home view.
                if (!browser_history.state.hash_before_overlay && overlays.settings_open()) {
                    browser_history.state.hash_before_overlay =
                        "#" +
                        (original_home_view === "recent_topics" ? "recent" : original_home_view);
                }
            }
            if (event.property === "twenty_four_hour_time") {
                // Recalculate timestamp column width
                message_lists.calculate_timestamp_widths();
                // Rerender the whole message list UI
                for (const msg_list of message_lists.all_rendered_message_lists()) {
                    msg_list.rerender();
                }
            }
            if (event.property === "high_contrast_mode") {
                $("body").toggleClass("high-contrast");
            }
            if (event.property === "demote_inactive_streams") {
                stream_list.update_streams_sidebar();
                stream_list_sort.set_filter_out_inactives();
            }
            if (event.property === "web_stream_unreads_count_display_policy") {
                stream_list.update_dom_unread_counts_visibility();
            }
            if (event.property === "user_list_style") {
                settings_preferences.report_user_list_style_change(
                    settings_preferences.user_settings_panel,
                );
                activity_ui.build_user_sidebar();
            }
            if (event.property === "dense_mode") {
                $("body").toggleClass("less-dense-mode");
                $("body").toggleClass("more-dense-mode");
            }
            if (
                event.property === "web_font_size_px" ||
                event.property === "web_line_height_percent"
            ) {
                information_density.set_base_typography_css_variables();
            }
            if (event.property === "web_mark_read_on_scroll_policy") {
                unread_ui.update_unread_banner();
            }
            if (event.property === "color_scheme") {
                requestAnimationFrame(() => {
                    if (event.value === settings_config.color_scheme_values.night.code) {
                        dark_theme.enable();
                        realm_logo.render();
                    } else if (event.value === settings_config.color_scheme_values.day.code) {
                        dark_theme.disable();
                        realm_logo.render();
                    } else {
                        dark_theme.default_preference_checker();
                        realm_logo.render();
                    }
                    message_lists.update_recipient_bar_background_color();
                });
            }
            if (event.property === "starred_message_counts") {
                starred_messages_ui.rerender_ui();
            }
            if (
                event.property === "receives_typing_notifications" &&
                !user_settings.receives_typing_notifications
            ) {
                typing_events.disable_typing_notification();
            }
            if (event.property === "fluid_layout_width") {
                scroll_bar.set_layout_width();
            }
            if (event.property === "default_language") {
                // TODO: Make this change the view immediately rather than
                // requiring a reload.  This is likely fairly difficult,
                // because various i18n strings are rendered by the
                // server; we may want to instead just trigger a page
                // reload.
            }
            if (event.property === "emojiset") {
                settings_preferences.report_emojiset_change(
                    settings_preferences.user_settings_panel,
                );
                // Rerender the whole message list UI
                for (const msg_list of message_lists.all_rendered_message_lists()) {
                    msg_list.rerender();
                }
                // Rerender buddy list status emoji
                activity_ui.build_user_sidebar();
            }

            if (event.property === "display_emoji_reaction_users") {
                message_live_update.rerender_messages_view();
            }
            if (event.property === "web_escape_navigates_to_home_view") {
                $("#go-to-home-view-hotkey-help").toggleClass("notdisplayed", !event.value);
            }
            if (event.property === "enter_sends") {
                user_settings.enter_sends = event.value;
                $(`.enter_sends_${!user_settings.enter_sends}`).hide();
                $(`.enter_sends_${user_settings.enter_sends}`).show();
                break;
            }
            if (event.property === "presence_enabled") {
                user_settings.presence_enabled = event.value;
                $("#user_presence_enabled").prop("checked", user_settings.presence_enabled);
                activity_ui.redraw_user(current_user.user_id);
                break;
            }
            if (event.property === "email_address_visibility") {
                user_settings.email_address_visibility = event.value;
                $("#user_email_address_visibility").val(event.value);
                break;
            }
            settings_preferences.update_page(event.property);
            break;
        }

        case "update_message_flags": {
            const new_value = event.op === "add";
            switch (event.flag) {
                case "starred":
                    for (const message_id of event.messages) {
                        starred_messages_ui.update_starred_flag(message_id, new_value);
                    }

                    if (event.op === "add") {
                        starred_messages.add(event.messages);
                        starred_messages_ui.rerender_ui();
                    } else {
                        starred_messages.remove(event.messages);
                        starred_messages_ui.rerender_ui();
                    }
                    break;
                case "read":
                    if (event.op === "add") {
                        unread_ops.process_read_messages_event(event.messages);
                    } else {
                        unread_ops.process_unread_messages_event({
                            message_ids: event.messages,
                            message_details: event.message_details,
                        });
                    }
                    break;
            }
            break;
        }

        case "user_group":
            switch (event.op) {
                case "add":
                    user_groups.add(event.group);
                    if (overlays.groups_open()) {
                        user_group_edit.add_group_to_table(event.group);
                    }
                    break;
                case "remove":
                    user_groups.remove(user_groups.get_user_group_from_id(event.group_id));
                    user_group_edit.handle_deleted_group(event.group_id);
                    break;
                case "add_members":
                    user_groups.add_members(event.group_id, event.user_ids);
                    user_group_edit.handle_member_edit_event(event.group_id, event.user_ids);
                    break;
                case "remove_members":
                    user_groups.remove_members(event.group_id, event.user_ids);
                    user_group_edit.handle_member_edit_event(event.group_id, event.user_ids);
                    break;
                case "add_subgroups":
                    user_groups.add_subgroups(event.group_id, event.direct_subgroup_ids);
                    break;
                case "remove_subgroups":
                    user_groups.remove_subgroups(event.group_id, event.direct_subgroup_ids);
                    break;
                case "update":
                    user_groups.update(event);
                    user_group_edit.update_group(event.group_id);
                    break;
                default:
                    blueslip.error("Unexpected event type user_group/" + event.op);
                    break;
            }
            break;

        case "user_status":
            if (event.status_text !== undefined) {
                user_status.set_status_text({
                    user_id: event.user_id,
                    status_text: event.status_text,
                });
                activity_ui.redraw_user(event.user_id);

                // Update the status text in compose box placeholder when opened to self.
                if (compose_pm_pill.get_user_ids().includes(event.user_id)) {
                    compose_recipient.update_placeholder_text();
                }
            }

            if (event.emoji_name !== undefined) {
                user_status.set_status_emoji(event);
                activity_ui.redraw_user(event.user_id);
                pm_list.update_private_messages();
                message_live_update.update_user_status_emoji(
                    event.user_id,
                    user_status.get_status_emoji(event.user_id),
                );
            }
            break;

        case "user_topic":
            user_topics_ui.handle_topic_updates(event);
            break;
    }
}
