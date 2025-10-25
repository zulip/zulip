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

    const audio_file_without_extension = "/static/audio/notification_sounds/" + notification_sound;

    $container_elem.empty();

    if (notification_sound !== "none") {
        // To create OGG source with src already set
        const $ogg_source = $("<source>")
            .addClass("notification-sound-source-ogg")
            .attr("type", "audio/ogg")
            .attr("src", `${audio_file_without_extension}.ogg`);

        // To create MP3 source with src already set
        const $mp3_source = $("<source>")
            .addClass("notification-sound-source-mp3")
            .attr("type", "audio/mpeg")
            .attr("src", `${audio_file_without_extension}.mp3`);

        // Add both sources to the audio element
        $container_elem.append($ogg_source, $mp3_source);

        // Load it so that it is ready to be played; without this the old sound
        // is played.
        util.the($container_elem).load();
    }
}
