import $ from "jquery";

import {user_settings} from "./user_settings";

export function initialize() {
    update_notification_sound_source($("#user-notification-sound-audio"), user_settings);
}

export function update_notification_sound_source($container_elem, settings_object) {
    const notification_sound = settings_object.notification_sound;
    const audio_file_without_extension = "/static/audio/notification_sounds/" + notification_sound;
    $container_elem
        .find(".notification-sound-source-ogg")
        .attr("src", `${audio_file_without_extension}.ogg`);
    $container_elem
        .find(".notification-sound-source-mp3")
        .attr("src", `${audio_file_without_extension}.mp3`);

    if (notification_sound !== "none") {
        // Load it so that it is ready to be played; without this the old sound
        // is played.
        $container_elem[0].load();
    }
}
