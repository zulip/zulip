import $ from "jquery";

import {user_settings} from "./user_settings";

export const notice_memory = new Map();

export let NotificationAPI;

export function set_notification_api(n) {
    NotificationAPI = n;
}

if (window.electron_bridge && window.electron_bridge.new_notification) {
    class ElectronBridgeNotification extends EventTarget {
        constructor(title, options) {
            super();
            Object.assign(
                this,
                window.electron_bridge.new_notification(title, options, (type, eventInit) =>
                    this.dispatchEvent(new Event(type, eventInit)),
                ),
            );
        }

        static get permission() {
            return Notification.permission;
        }

        static async requestPermission(callback) {
            if (callback) {
                callback(await Promise.resolve(Notification.permission));
            }
            return Notification.permission;
        }
    }

    NotificationAPI = ElectronBridgeNotification;
} else if (window.Notification) {
    NotificationAPI = window.Notification;
}

export function get_notifications() {
    return notice_memory;
}

export function initialize() {
    $(window).on("focus", () => {
        for (const notice_mem_entry of notice_memory.values()) {
            notice_mem_entry.obj.close();
        }
        notice_memory.clear();
    });

    update_notification_sound_source($("#user-notification-sound-audio"), user_settings);
}

export function update_notification_sound_source(container_elem, settings_object) {
    const notification_sound = settings_object.notification_sound;
    const audio_file_without_extension = "/static/audio/notification_sounds/" + notification_sound;
    container_elem
        .find(".notification-sound-source-ogg")
        .attr("src", `${audio_file_without_extension}.ogg`);
    container_elem
        .find(".notification-sound-source-mp3")
        .attr("src", `${audio_file_without_extension}.mp3`);

    if (notification_sound !== "none") {
        // Load it so that it is ready to be played; without this the old sound
        // is played.
        container_elem[0].load();
    }
}

export function permission_state() {
    if (NotificationAPI === undefined) {
        // act like notifications are blocked if they do not have access to
        // the notification API.
        return "denied";
    }
    return NotificationAPI.permission;
}

export function close_notification(message) {
    for (const [key, notice_mem_entry] of notice_memory) {
        if (notice_mem_entry.message_id === message.id) {
            notice_mem_entry.obj.close();
            notice_memory.delete(key);
        }
    }
}

export function granted_desktop_notifications_permission() {
    return NotificationAPI && NotificationAPI.permission === "granted";
}

export function request_desktop_notifications_permission() {
    if (NotificationAPI) {
        NotificationAPI.requestPermission();
    }
}
