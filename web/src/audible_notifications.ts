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
    // Sanitize to prevent injection (allow only alphanumeric, dash, underscore)
    const safe_notification_sound = notification_sound.replace(/[^a-zA-Z0-9_-]/g, "");
    const audio_file_without_extension =
        "/static/audio/notification_sounds/" + safe_notification_sound;

    // If the audio element isn't present yet, nothing to update.
    if ($container_elem.length === 0) {
        return;
    }

    // Ensure source elements exist so we can set their src attributes safely.
    let $ogg = $container_elem.find(".notification-sound-source-ogg");
    if ($ogg.length === 0) {
        $ogg = $("<source>")
            .addClass("notification-sound-source-ogg")
            .attr("type", "audio/ogg")
            .appendTo($container_elem);
    }

    let $mp3 = $container_elem.find(".notification-sound-source-mp3");
    if ($mp3.length === 0) {
        $mp3 = $("<source>")
            .addClass("notification-sound-source-mp3")
            .attr("type", "audio/mpeg")
            .appendTo($container_elem);
    }

    if (safe_notification_sound !== "none" && safe_notification_sound !== "") {
        $ogg.attr("src", `${audio_file_without_extension}.ogg`);
        $mp3.attr("src", `${audio_file_without_extension}.mp3`);

        // Load the audio so it's ready to play.
        util.the($container_elem).load();
    } else {
        // Clear sources to avoid attempting to load a "none" file.
        $ogg.removeAttr("src");
        $mp3.removeAttr("src");
        try {
            util.the($container_elem).pause();
            util.the($container_elem).currentTime = 0;
        } catch {
            // ignore if pause/currentTime not available
        }
    }
}