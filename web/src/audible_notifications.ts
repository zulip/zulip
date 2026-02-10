import $ from "jquery";

import render_notification_sound_sources from "../templates/notification_sound_sources.hbs";

import {user_settings} from "./user_settings.ts";
import * as util from "./util.ts";

export function initialize(): void {
    update_notification_sound_source("user-notification-sound-audio", user_settings);
}

export function update_notification_sound_source(
    audio_element_id: string,
    settings_object: {notification_sound: string},
): void {
    const notification_sound = settings_object.notification_sound;
    const $container_elem = $<HTMLAudioElement>(`audio#${CSS.escape(audio_element_id)}`);

    if (notification_sound === "none") {
        $container_elem.empty();
        return;
    }

    const audio_file_without_extension = "/static/audio/notification_sounds/" + notification_sound;
    const rendered_audio = render_notification_sound_sources({
        audio_element_id,
        audio_file_ogg: `${audio_file_without_extension}.ogg`,
        audio_file_mp3: `${audio_file_without_extension}.mp3`,
    });
    $container_elem.replaceWith($(rendered_audio));

    // Load it so that it is ready to be played; without this the old sound
    // is played.
    util.the($<HTMLAudioElement>(`audio#${CSS.escape(audio_element_id)}`)).load();
}
