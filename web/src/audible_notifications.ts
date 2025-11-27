import $ from "jquery";

import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

export function initialize(): void {
    update_notification_sound_source($("audio#user-notification-sound-audio"), user_settings);
}

export function update_notification_sound_source(
    $container_elem: JQuery<HTMLAudioElement>,
    settings_object: {notification_sound: string},
): void {
    const notification_sound = settings_object.notification_sound;

    // Return early if the audio element doesn't exist
    if ($container_elem.length === 0) {
        return;
    }

    // Sanitize notification_sound to prevent any injection (allow only alphanumeric, dash, underscore)
    const safe_notification_sound = notification_sound.replaceAll(/[^a-zA-Z0-9_-]/g, "");
    const audio_file_without_extension =
        "/static/audio/notification_sounds/" + safe_notification_sound;

    // Clear any existing source elements
    $container_elem.empty();

    if (safe_notification_sound !== "none" && safe_notification_sound !== "") {
        // Create OGG source element with src already set
        const ogg_source = document.createElement("source");
        ogg_source.className = "notification-sound-source-ogg";
        ogg_source.type = "audio/ogg";
        ogg_source.src = `${audio_file_without_extension}.ogg`;

        // Create MP3 source element with src already set
        const mp3_source = document.createElement("source");
        mp3_source.className = "notification-sound-source-mp3";
        mp3_source.type = "audio/mpeg";
        mp3_source.src = `${audio_file_without_extension}.mp3`;

        // Add both sources to the audio element using native DOM
        const container_elem = util.the($container_elem);
        container_elem.append(ogg_source, mp3_source);

        // Load it so that it is ready to be played; without this the old sound
        // is played.
        container_elem.load();
    }
}
