import $ from "jquery";

import * as activity_ui from "./activity_ui.ts";
import * as alert_words from "./alert_words.ts";
import * as alert_words_ui from "./alert_words_ui.ts";
import * as attachments_ui from "./attachments_ui.ts";
import * as audible_notifications from "./audible_notifications.ts";
import * as blueslip from "./blueslip.ts";
import * as bot_data from "./bot_data.ts";
import * as browser_history from "./browser_history.ts";
import {buddy_list} from "./buddy_list.ts";
import * as channel_folders from "./channel_folders.ts";
import * as compose_call from "./compose_call.ts";
import * as compose_call_ui from "./compose_call_ui.ts";
import * as compose_closed_ui from "./compose_closed_ui.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_validate from "./compose_validate.ts";
import {electron_bridge} from "./electron_bridge.ts";
import * as emoji from "./emoji.ts";
import * as emoji_picker from "./emoji_picker.ts";
import * as gear_menu from "./gear_menu.ts";
import * as giphy from "./giphy.ts";
import * as inbox_ui from "./inbox_ui.ts";
import * as information_density from "./information_density.ts";
import * as left_sidebar_navigation_area from "./left_sidebar_navigation_area.ts";
import * as linkifiers from "./linkifiers.ts";
import * as message_edit from "./message_edit.ts";
import * as message_events from "./message_events.ts";
import * as message_lists from "./message_lists.ts";
import * as message_live_update from "./message_live_update.ts";
import * as message_reminder from "./message_reminder.ts";
import * as message_store from "./message_store.ts";
import * as message_view from "./message_view.ts";
import * as muted_users_ui from "./muted_users_ui.ts";
import * as narrow_title from "./narrow_title.ts";
import * as navbar_alerts from "./navbar_alerts.ts";
import * as navigation_views from "./navigation_views.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import * as overlays from "./overlays.ts";
import * as peer_data from "./peer_data.ts";
import * as people from "./people.ts";
import * as pm_list from "./pm_list.ts";
import * as reactions from "./reactions.ts";
import * as realm_icon from "./realm_icon.ts";
import * as realm_logo from "./realm_logo.ts";
import * as realm_playground from "./realm_playground.ts";
import {realm_user_settings_defaults} from "./realm_user_settings_defaults.ts";
import * as recent_view_ui from "./recent_view_ui.ts";
import * as reload from "./reload.ts";
import * as reminders_overlay_ui from "./reminders_overlay_ui.ts";
import * as saved_snippets from "./saved_snippets.ts";
import * as saved_snippets_ui from "./saved_snippets_ui.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as scheduled_messages_feed_ui from "./scheduled_messages_feed_ui.ts";
import * as scheduled_messages_overlay_ui from "./scheduled_messages_overlay_ui.ts";
import * as scheduled_messages_ui from "./scheduled_messages_ui.ts";
import * as scroll_bar from "./scroll_bar.ts";
import * as settings_account from "./settings_account.ts";
import * as settings_bots from "./settings_bots.ts";
import * as settings_components from "./settings_components.ts";
import * as settings_config from "./settings_config.ts";
import * as settings_emoji from "./settings_emoji.ts";
import * as settings_exports from "./settings_exports.ts";
import * as settings_folders from "./settings_folders.ts";
import * as settings_invites from "./settings_invites.ts";
import * as settings_linkifiers from "./settings_linkifiers.ts";
import * as settings_notifications from "./settings_notifications.ts";
import * as settings_org from "./settings_org.ts";
import * as settings_playgrounds from "./settings_playgrounds.ts";
import * as settings_preferences from "./settings_preferences.ts";
import * as settings_profile_fields from "./settings_profile_fields.ts";
import * as settings_realm_domains from "./settings_realm_domains.ts";
import * as settings_realm_user_settings_defaults from "./settings_realm_user_settings_defaults.ts";
import * as settings_streams from "./settings_streams.ts";
import * as sidebar_ui from "./sidebar_ui.ts";
import * as starred_messages from "./starred_messages.ts";
import * as starred_messages_ui from "./starred_messages_ui.ts";
import {current_user, realm} from "./state_data.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_events from "./stream_events.ts";
import * as stream_list from "./stream_list.ts";
import * as stream_list_sort from "./stream_list_sort.ts";
import * as stream_settings_components from "./stream_settings_components.ts";
import * as stream_settings_data from "./stream_settings_data.ts";
import * as stream_settings_ui from "./stream_settings_ui.ts";
import * as stream_topic_history from "./stream_topic_history.ts";
import * as stream_ui_updates from "./stream_ui_updates.ts";
import * as sub_store from "./sub_store.ts";
import * as submessage from "./submessage.ts";
import * as theme from "./theme.ts";
import {group_setting_value_schema} from "./types.ts";
import * as typing_events from "./typing_events.ts";
import * as unread_ops from "./unread_ops.ts";
import * as unread_ui from "./unread_ui.ts";
import * as user_events from "./user_events.ts";
import * as user_group_edit from "./user_group_edit.ts";
import * as user_groups from "./user_groups.ts";
import {user_settings} from "./user_settings.ts";
import * as user_status from "./user_status.ts";
import * as user_topics from "./user_topics.ts";
import * as user_topics_ui from "./user_topics_ui.ts";

export function dispatch_normal_event(event) {
    const noop = function () {
        // Do nothing
    };

    switch (event.type) {
        case "alert_words":
            alert_words.set_words(event.alert_words);
            alert_words_ui.rerender_alert_words_ui();
            break;

        case "attachment":
            attachments_ui.update_attachments(event);
            break;

        case "channel_folder":
            switch (event.op) {
                case "add": {
                    channel_folders.add(event.channel_folder);
                    inbox_ui.complete_rerender();
                    settings_folders.populate_channel_folders();
                    stream_ui_updates.update_folder_dropdown_visibility();
                    break;
                }
                case "update":
                    channel_folders.update(event);
                    if (event.data.name !== undefined) {
                        inbox_ui.complete_rerender();
                        stream_list.update_streams_sidebar();
                        stream_settings_ui.update_channel_folder_name(event.channel_folder_id);
                    }

                    if (event.data.is_archived !== undefined) {
                        stream_settings_ui.reset_dropdown_set_to_archived_folder(
                            event.channel_folder_id,
                        );
                        stream_ui_updates.update_folder_dropdown_visibility();
                    }
                    settings_folders.update_folder_row(event);
                    break;
                case "reorder":
                    channel_folders.reorder(event.order);
                    stream_list.update_streams_sidebar();
                    settings_folders.populate_channel_folders();
                    inbox_ui.complete_rerender();
                    break;
                default:
                    blueslip.error("Unexpected event type channel_folder/" + event.op);
                    break;
            }
            break;

        case "custom_profile_fields":
            realm.custom_profile_fields = event.fields;
            settings_profile_fields.populate_profile_fields(realm.custom_profile_fields);
            settings_account.add_custom_profile_fields_to_settings();
            navbar_alerts.maybe_toggle_empty_required_profile_fields_banner();
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
            onboarding_steps.update_onboarding_steps_to_display(event.onboarding_steps);
            break;

        case "invites_changed":
            if ($("#admin-invites-list").length > 0) {
                settings_invites.set_up(false);
            }
            break;

        case "muted_users":
            muted_users_ui.handle_user_updates(event.muted_users);
            break;

        case "navigation_view":
            switch (event.op) {
                case "add":
                    navigation_views.add_navigation_view(event.navigation_view);
                    break;
                case "update":
                    navigation_views.update_navigation_view(event.fragment, event.data);
                    break;
                case "remove":
                    navigation_views.remove_navigation_view(event.fragment);
                    break;
            }
            break;

        case "presence":
            activity_ui.update_presence_info(event.presences);
            break;

        case "restart":
            realm.zulip_version = event.zulip_version;
            realm.zulip_merge_base = event.zulip_merge_base;
            break;

        case "web_reload_client": {
            const reload_options = {
                save_compose: true,
                reason: "update",
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
            message_events.update_views_filtered_on_message_property(
                [event.message_id],
                "has-reaction",
                event.op === "add",
            );
            break;

        case "realm": {
            const realm_settings = {
                allow_message_editing: noop,
                avatar_changes_disabled: settings_account.update_avatar_change_display,
                can_access_all_users_group: noop,
                can_add_custom_emoji_group: settings_emoji.update_custom_emoji_ui,
                can_add_subscribers_group: noop,
                can_create_bots_group: settings_bots.update_bot_permissions_ui,
                can_create_groups: user_group_edit.update_group_creation_ui,
                can_create_private_channel_group: noop,
                can_create_public_channel_group: noop,
                can_create_web_public_channel_group: noop,
                can_create_write_only_bots_group: settings_bots.update_bot_permissions_ui,
                can_delete_any_message_group: noop,
                can_delete_own_message_group: noop,
                can_invite_users_group: noop,
                can_manage_all_groups: user_group_edit.update_group_management_ui,
                can_manage_billing_group: noop,
                can_mention_many_users_group: noop,
                can_move_messages_between_channels_group: noop,
                can_move_messages_between_topics_group: noop,
                can_resolve_topics_group: noop,
                can_set_delete_message_policy_group: noop,
                can_set_topics_policy_group: noop,
                can_summarize_topics_group: noop,
                create_multiuse_invite_group: noop,
                default_code_block_language: noop,
                default_language: noop,
                description: noop,
                digest_emails_enabled: noop,
                digest_weekday: noop,
                direct_message_initiator_group: noop,
                direct_message_permission_group: noop,
                email_changes_disabled: settings_account.update_email_change_display,
                disallow_disposable_email_addresses: noop,
                inline_image_preview: noop,
                inline_url_embed_preview: noop,
                invite_required: noop,
                message_content_edit_limit_seconds: noop,
                message_content_delete_limit_seconds: noop,
                message_edit_history_visibility_policy: noop,
                moderation_request_channel_id: noop,
                move_messages_between_streams_limit_seconds: noop,
                move_messages_within_stream_limit_seconds: message_edit.update_inline_topic_edit_ui,
                message_retention_days: noop,
                name: narrow_title.redraw_title,
                name_changes_disabled: settings_account.update_name_change_display,
                new_stream_announcements_stream_id: stream_ui_updates.update_announce_stream_option,
                org_type: noop,
                push_notifications_enabled: noop,
                require_unique_names: noop,
                send_welcome_emails: noop,
                topics_policy: noop,
                require_e2ee_push_notifications: noop,
                message_content_allowed_in_email_notifications: noop,
                enable_spectator_access: noop,
                send_channel_events_messages: noop,
                signup_announcements_stream_id: noop,
                zulip_update_announcements_stream_id: noop,
                emails_restricted_to_domains: noop,
                video_chat_provider: compose_call_ui.update_audio_and_video_chat_button_display,
                jitsi_server_url: compose_call_ui.update_audio_and_video_chat_button_display,
                giphy_rating: giphy.update_giphy_rating,
                waiting_period_threshold: noop,
                want_advertise_in_communities_directory: noop,
                welcome_message_custom_text: noop,
                enable_read_receipts: settings_account.update_send_read_receipts_tooltip,
                enable_guest_user_dm_warning: compose_validate.warn_if_guest_in_dm_recipient,
                enable_guest_user_indicator: noop,
            };
            switch (event.op) {
                case "update":
                    if (Object.hasOwn(realm_settings, event.property)) {
                        realm["realm_" + event.property] = event.value;
                        realm_settings[event.property]();
                        settings_org.sync_realm_settings(event.property);

                        if (event.property === "name") {
                            electron_bridge?.send_event("realm_name", event.value);
                        }

                        if (event.property === "enable_spectator_access") {
                            stream_ui_updates.update_stream_privacy_choices(
                                "can_create_web_public_channel_group",
                            );
                        }
                    }
                    break;
                case "update_dict":
                    switch (event.property) {
                        case "default":
                            for (const [key, value] of Object.entries(event.data)) {
                                if (key === "max_file_upload_size_mib") {
                                    realm[key] = value;
                                } else {
                                    realm["realm_" + key] = value;
                                }

                                if (key === "topics_policy") {
                                    compose_recipient.update_topic_inputbox_on_topics_policy_change();
                                    compose_recipient.update_compose_area_placeholder_text();
                                }

                                if (Object.hasOwn(realm_settings, key)) {
                                    settings_org.sync_realm_settings(key);
                                    realm_settings[key]();
                                }

                                if (
                                    Object.keys(
                                        realm.server_supported_permission_settings.realm,
                                    ).includes(key)
                                ) {
                                    user_group_edit.update_realm_setting_in_permissions_panel(
                                        key,
                                        group_setting_value_schema.parse(value),
                                    );
                                }

                                if (
                                    key === "create_multiuse_invite_group" ||
                                    key === "can_invite_users_group"
                                ) {
                                    settings_invites.update_invite_user_panel();
                                    sidebar_ui.update_invite_user_option();
                                    gear_menu.rerender();
                                }

                                if (
                                    key === "can_create_public_channel_group" ||
                                    key === "can_create_private_channel_group" ||
                                    key === "can_create_web_public_channel_group"
                                ) {
                                    stream_ui_updates.update_stream_privacy_choices(key);
                                }

                                if (
                                    key === "direct_message_initiator_group" ||
                                    key === "direct_message_permission_group"
                                ) {
                                    settings_org.check_disable_direct_message_initiator_group_widget();
                                    compose_closed_ui.maybe_update_buttons_for_dm_recipient();
                                    compose_validate.validate_and_update_send_button_status();
                                }

                                if (
                                    key === "can_move_messages_between_topics_group" ||
                                    key === "can_resolve_topics_group"
                                ) {
                                    // Technically we just need to rerender the message recipient
                                    // bars to update the buttons for editing or resolving a topic,
                                    // but because these policies are changed rarely, it's fine to
                                    // rerender the entire message feed.
                                    message_live_update.rerender_messages_view();
                                }

                                if (key === "plan_type") {
                                    gear_menu.rerender();
                                }

                                if (
                                    key === "can_add_subscribers_group" &&
                                    overlays.streams_open()
                                ) {
                                    const active_stream_id =
                                        stream_settings_components.get_active_data().id;
                                    if (active_stream_id !== undefined) {
                                        const slim_sub = sub_store.get(active_stream_id);
                                        const sub =
                                            stream_settings_data.get_sub_for_settings(slim_sub);
                                        stream_ui_updates.update_add_subscriptions_elements(sub);
                                    }
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
                            electron_bridge?.send_event("realm_icon_url", event.data.icon_url);
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
                navbar_alerts.toggle_organization_profile_incomplete_banner();
            }
            break;
        }

        case "realm_bot":
            switch (event.op) {
                case "add":
                    bot_data.add(event.bot);
                    if (event.bot.owner_id === current_user.user_id) {
                        settings_bots.redraw_your_bots_list();
                        settings_bots.toggle_bot_config_download_container();
                    }
                    break;
                case "delete":
                    bot_data.del(event.bot.user_id);
                    settings_bots.redraw_your_bots_list();
                    settings_bots.toggle_bot_config_download_container();
                    break;
                case "update":
                    bot_data.update(event.bot.user_id, event.bot);
                    if ("owner_id" in event.bot) {
                        settings_bots.redraw_your_bots_list();
                        settings_bots.toggle_bot_config_download_container();
                    }
                    if ("is_active" in event.bot) {
                        settings_bots.toggle_bot_config_download_container();
                    }
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

        case "realm_export_consent":
            settings_exports.update_export_consent_data_and_redraw({
                user_id: event.user_id,
                consented: event.consented,
            });
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
                case "add": {
                    // There may be presence data we already received from the server
                    // before getting this event. Check if we need to redraw.
                    const should_redraw = activity_ui.check_should_redraw_new_user(
                        event.person.user_id,
                    );

                    people.add_active_user(event.person, "server_events");
                    settings_account.maybe_update_deactivate_account_button();
                    if (event.person.is_bot) {
                        settings_bots.redraw_all_bots_list();
                    }

                    if (should_redraw) {
                        activity_ui.redraw_user(event.person.user_id);
                    }

                    if (!event.person.is_bot) {
                        settings_exports.update_export_consent_data_and_redraw({
                            user_id: event.person.user_id,
                            consented: false,
                        });
                    }
                    break;
                }
                case "update":
                    user_events.update_person(event.person);
                    settings_account.maybe_update_deactivate_account_button();
                    if (people.is_valid_bot_user(event.person.user_id)) {
                        settings_bots.update_bot_data(event.person.user_id);
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

        case "saved_snippets":
            switch (event.op) {
                case "add":
                    saved_snippets.update_saved_snippet_dict(event.saved_snippet);
                    saved_snippets_ui.rerender_dropdown_widget();
                    break;
                case "remove":
                    saved_snippets.remove_saved_snippet(event.saved_snippet_id);
                    saved_snippets_ui.rerender_dropdown_widget();
                    break;
                case "update":
                    saved_snippets.update_saved_snippet_dict(event.saved_snippet);
                    saved_snippets_ui.rerender_dropdown_widget();
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

        case "reminders":
            switch (event.op) {
                case "add": {
                    message_reminder.add_reminders(event.reminders);
                    reminders_overlay_ui.rerender();
                    left_sidebar_navigation_area.update_reminders_row();
                    break;
                }
                case "remove": {
                    message_reminder.remove_reminder(event.reminder_id);
                    reminders_overlay_ui.remove_reminder_id(event.reminder_id);
                    left_sidebar_navigation_area.update_reminders_row();
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
                    for (const stream_id of event.stream_ids) {
                        const was_subscribed = sub_store.get(stream_id).subscribed;
                        stream_data.delete_sub(stream_id);
                        stream_settings_ui.remove_stream(stream_id);
                        if (was_subscribed) {
                            stream_list.remove_sidebar_row(stream_id);
                            if (stream_id === compose_state.selected_recipient_id) {
                                compose_state.set_selected_recipient_id("");
                                compose_recipient.on_compose_select_recipient_update();
                            }
                        }
                        settings_streams.update_default_streams_table();
                        stream_data.remove_default_stream(stream_id);
                        if (realm.realm_moderation_request_channel_id === stream_id) {
                            settings_org.sync_realm_settings("moderation_request_channel_id");
                        }
                        if (realm.realm_new_stream_announcements_stream_id === stream_id) {
                            settings_org.sync_realm_settings("new_stream_announcements_stream_id");
                        }
                        if (realm.realm_signup_announcements_stream_id === stream_id) {
                            settings_org.sync_realm_settings("signup_announcements_stream_id");
                        }
                        if (realm.realm_zulip_update_announcements_stream_id === stream_id) {
                            settings_org.sync_realm_settings(
                                "zulip_update_announcements_stream_id",
                            );
                        }
                        const message_ids = message_store.get_message_ids_in_stream(stream_id);
                        unread_ops.process_read_messages_event(message_ids);
                        message_events.remove_messages(message_ids);
                        stream_topic_history.remove_history_for_stream(stream_id);
                        user_group_edit.update_group_permissions_panel_on_losing_stream_access(
                            stream_id,
                        );
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

        case "typing_edit_message":
            if (event.sender_id === current_user.user_id) {
                // typing edit message notifications are sent to the user who is typing
                // as well as recipients; we ignore such self-generated events.
                return;
            }
            switch (event.op) {
                case "start":
                    typing_events.display_message_edit_notification(event);
                    break;
                case "stop":
                    typing_events.hide_message_edit_notification(event);
                    break;
                default:
                    blueslip.error("Unexpected event type typing_edit_message/" + event.op);
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

            // TODO/typescript: Move privacy_setting_name_schema and PrivacySettingName
            // here from `settings_account` when this file is converted to typescript,
            // and use them instead of `privacy_settings`.
            const privacy_settings = [
                "allow_private_data_export",
                "email_address_visibility",
                "presence_enabled",
                "send_private_typing_notifications",
                "send_read_receipts",
                "send_stream_typing_notifications",
            ];

            if (privacy_settings.includes(event.property)) {
                user_settings[event.property] = event.value;
                settings_account.update_privacy_settings_box(event.property);
                if (event.property === "presence_enabled") {
                    activity_ui.redraw_user(current_user.user_id);
                }
                if (event.property === "allow_private_data_export") {
                    settings_exports.refresh_allow_private_data_export_banner();
                }
                break;
            }

            const user_preferences = [
                "color_scheme",
                "default_language",
                "demote_inactive_streams",
                "display_emoji_reaction_users",
                "emojiset",
                "enter_sends",
                "fluid_layout_width",
                "hide_ai_features",
                "high_contrast_mode",
                "receives_typing_notifications",
                "resolved_topic_notice_auto_read_policy",
                "starred_message_counts",
                "timezone",
                "translate_emoticons",
                "twenty_four_hour_time",
                "user_list_style",
                "web_animate_image_previews",
                "web_channel_default_view",
                "web_escape_navigates_to_home_view",
                "web_home_view",
                "web_mark_read_on_scroll_policy",
                "web_navigate_to_sent_message",
                "web_stream_unreads_count_display_policy",
                "web_suggest_update_timezone",
                "web_left_sidebar_unreads_count_summary",
                "web_left_sidebar_show_channel_folders",
                "web_inbox_show_channel_folders",
            ];

            const original_home_view = user_settings.web_home_view;
            if (user_preferences.includes(event.property)) {
                user_settings[event.property] = event.value;
            }
            if (event.property === "default_language") {
                // We additionally need to set the language name.
                //
                // Note that this does not change translations at all;
                // a reload is fundamentally required because we
                // cannot rerender with the new language the strings
                // present in the backend/Jinja2 templates.
                settings_preferences.set_default_language(event.value);
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
                information_density.calculate_timestamp_widths();
                // Rerender the whole message list UI
                for (const msg_list of message_lists.all_rendered_message_lists()) {
                    msg_list.rerender();
                }
            }
            if (event.property === "high_contrast_mode") {
                $("body").toggleClass("high-contrast", event.value);
            }
            if (event.property === "demote_inactive_streams") {
                stream_list_sort.set_filter_out_inactives();
                stream_list.update_streams_sidebar(true);
            }
            if (event.property === "web_animate_image_previews") {
                // Rerender the whole message list UI
                for (const msg_list of message_lists.all_rendered_message_lists()) {
                    msg_list.rerender();
                }
            }
            if (event.property === "web_stream_unreads_count_display_policy") {
                stream_list.build_stream_list(true);
            }
            if (event.property === "user_list_style") {
                settings_preferences.report_user_list_style_change(
                    settings_preferences.user_settings_panel,
                );
                activity_ui.build_user_sidebar();
            }
            if (
                event.property === "web_font_size_px" ||
                event.property === "web_line_height_percent"
            ) {
                // We just ignore events for web_font_size_px"
                // and "web_line_height_percent" settings as we
                // are fine with a window not being updated due
                // to changes being done from another window and
                // also helps in avoiding weird issues on clicking
                // the "+"/"-" buttons multiple times quickly when
                // updating these settings.
            }

            if (event.property === "web_mark_read_on_scroll_policy") {
                unread_ui.update_unread_banner();
            }
            if (event.property === "color_scheme") {
                requestAnimationFrame(() => {
                    theme.set_theme_and_update(event.value);
                });
            }
            if (event.property === "starred_message_counts") {
                starred_messages_ui.rerender_ui();
            }
            if (event.property === "web_left_sidebar_unreads_count_summary") {
                stream_list.update_unread_counts_visibility();
            }
            if (event.property === "web_left_sidebar_show_channel_folders") {
                stream_list.build_stream_list(true);
            }
            if (event.property === "web_inbox_show_channel_folders") {
                inbox_ui.complete_rerender();
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
                $("#keyboard-shortcuts .go-to-home-view-hotkey-help").toggleClass(
                    "notdisplayed",
                    !event.value,
                );
            }
            if (event.property === "web_suggest_update_timezone") {
                $("#automatically_offer_update_time_zone").prop("checked", event.value);
            }
            if (event.property === "web_channel_default_view") {
                // We need to rerender wherever `channel_url_by_user_setting` is used in the DOM.
                // Left sidebar
                const force_rerender = true;
                stream_list.create_initial_sidebar_rows(force_rerender);
                stream_list.update_streams_sidebar(force_rerender);
                // Inbox View
                inbox_ui.complete_rerender();
                // Recent View
                recent_view_ui.complete_rerender();
                // Message feed
                for (const msg_list of message_lists.all_rendered_message_lists()) {
                    msg_list.rerender();
                }
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
                    message_events.update_views_filtered_on_message_property(
                        event.messages,
                        "is-starred",
                        new_value,
                    );
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
                    message_events.update_views_filtered_on_message_property(
                        event.messages,
                        "is-unread",
                        new_value,
                    );
                    break;
            }
            break;
        }

        case "user_group":
            switch (event.op) {
                case "add": {
                    const user_group = user_groups.add(event.group);
                    if (overlays.groups_open()) {
                        user_group_edit.add_group_to_table(user_group);
                    }
                    break;
                }
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
                    user_group_edit.handle_subgroup_edit_event(
                        event.group_id,
                        event.direct_subgroup_ids,
                    );
                    break;
                case "remove_subgroups":
                    user_groups.remove_subgroups(event.group_id, event.direct_subgroup_ids);
                    user_group_edit.handle_subgroup_edit_event(
                        event.group_id,
                        event.direct_subgroup_ids,
                    );
                    break;
                case "update": {
                    const group_id = event.group_id;
                    const group = user_groups.get_user_group_from_id(group_id);
                    user_groups.update(event, group);
                    user_group_edit.update_group(event, group);
                    break;
                }
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
                    compose_recipient.update_compose_area_placeholder_text();
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

        case "user_topic": {
            const previous_topic_visibility = user_topics.get_topic_visibility_policy(
                event.stream_id,
                event.topic_name,
            );
            user_topics_ui.handle_topic_updates(
                event,
                message_events.update_current_view_for_topic_visibility(),
                message_view.rerender_combined_feed,
            );
            // Discard cached message lists if `event` topic was / is followed.
            if (
                event.visibility_policy === user_topics.all_visibility_policies.FOLLOWED ||
                previous_topic_visibility === user_topics.all_visibility_policies.FOLLOWED
            ) {
                message_events.discard_cached_lists_with_term_type("is-followed");
            }
            break;
        }
    }
}
