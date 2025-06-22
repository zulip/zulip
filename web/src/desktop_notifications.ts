import {$} from "jquery";
import assert from "minimalistic-assert";

import {electron_bridge} from "./electron_bridge.ts";
import {$t} from "./i18n.ts";
import * as message_parser from "./message_parser.ts";
import * as spoilers from "./spoilers.ts";
import * as ui_util from "./ui_util.ts";
import {user_settings} from "./user_settings.ts";

type NoticeMemory = Map<
    string,
    {
        obj: Notification | ElectronBridgeNotification;
        msg_count: number;
        message_id: number;
        on_close?: (() => void) | undefined;
    }
>;

export const notice_memory: NoticeMemory = new Map();

export let NotificationAPI: typeof ElectronBridgeNotification | typeof Notification | undefined;

// Used for testing
export function set_notification_api(n: typeof NotificationAPI): void {
    NotificationAPI = n;
}

export class ElectronBridgeNotification extends EventTarget {
    title: string;
    dir: NotificationDirection;
    lang: string;
    body: string;
    tag: string;
    icon: string;
    data: unknown;
    close: () => void;

    constructor(title: string, options: NotificationOptions) {
        super();
        assert(electron_bridge?.new_notification !== undefined);
        const notification_data = electron_bridge.new_notification(
            title,
            options,
            (type, eventInit) => this.dispatchEvent(new Event(type, eventInit)),
        );
        this.title = notification_data.title;
        this.dir = notification_data.dir;
        this.lang = notification_data.lang;
        this.body = notification_data.body;
        this.tag = notification_data.tag;
        this.icon = notification_data.icon;
        this.data = notification_data.data;
        this.close = notification_data.close;
    }

    static get permission(): NotificationPermission {
        return Notification.permission;
    }

    static async requestPermission(
        callback?: (permission: NotificationPermission) => void,
    ): Promise<NotificationPermission> {
        if (callback) {
            callback(await Promise.resolve(Notification.permission));
        }
        return Notification.permission;
    }
}

if (electron_bridge?.new_notification) {
    NotificationAPI = ElectronBridgeNotification;
} else if (window.Notification) {
    NotificationAPI = window.Notification;
}

export type NotificationType = "message" | "reaction";

// The parts of a message that the notification body is built from. This
// is structural rather than `Message`, since the test notifications
// message_notifications sends are not real messages.
export type NotificationContentMessage = {
    content: string;
    sender_full_name: string;
    type: "stream" | "private" | "test-notification";
    is_me_message?: boolean | undefined;
};

export function get_notification_content(
    message: NotificationContentMessage,
    notification_type: NotificationType,
): string {
    let content;
    // Convert the content to plain text, replacing emoji with their alt text
    const $content = $("<div>").html(message.content);
    ui_util.convert_unicode_eligible_emoji_to_unicode($content);
    ui_util.change_katex_to_raw_latex($content);
    ui_util.potentially_collapse_quotes($content);
    spoilers.hide_spoilers_in_notification($content);

    if (
        $content.text().trim() === "" &&
        (message_parser.message_has_image(message.content) ||
            message_parser.message_has_attachment(message.content))
    ) {
        content = $t({defaultMessage: "(attached file)"});
    } else {
        content = $content.text();
    }

    if (message.is_me_message) {
        content = message.sender_full_name + content.slice(3);
    }

    if (
        (message.type === "private" || message.type === "test-notification") &&
        !user_settings.pm_content_in_desktop_notifications
    ) {
        if (notification_type === "reaction") {
            return "";
        }

        content = $t(
            {defaultMessage: "New direct message from {sender_full_name}"},
            {sender_full_name: message.sender_full_name},
        );
    }

    return content;
}

export function create_notification(opts: {
    notification_options: NotificationOptions;
    key: string;
    title: string;
    message_id: number;
    msg_count: number;
    on_click?: (() => void) | undefined;
    on_close?: (() => void) | undefined;
}): void {
    const {notification_options, key, title, message_id, msg_count, on_click, on_close} = opts;

    assert(NotificationAPI !== undefined);
    const notification_object = new NotificationAPI(title, notification_options);
    notice_memory.set(key, {
        obj: notification_object,
        msg_count,
        message_id,
        // Ideally, we would let the close event handler call this and
        // wouldn't need to store it in notice_memory. However, since
        // event handlers aren't available in some cases, we need to
        // call this manually after calling close().
        on_close,
    });

    if (typeof notification_object.addEventListener === "function") {
        // Sadly, some third-party Electron apps like Franz/Ferdi
        // misimplement the Notification API not inheriting from
        // EventTarget.  This results in addEventListener being
        // unavailable for them.
        notification_object.addEventListener("click", () => {
            notification_object.close();
            on_click?.();
            window.focus();
        });
        notification_object.addEventListener("close", () => {
            const current_notice_memory = notice_memory.get(key);
            // This check helps avoid race between close event for current notification
            // object and the previous notification_object close handler.
            if (current_notice_memory?.obj === notification_object) {
                notice_memory.delete(key);
                on_close?.();
            }
        });
    }
}

export function get_notifications(): NoticeMemory {
    return notice_memory;
}

export function initialize(): void {
    $(window).on("focus", () => {
        for (const notice_mem_entry of notice_memory.values()) {
            notice_mem_entry.obj.close();
            notice_mem_entry.on_close?.();
        }
        notice_memory.clear();
    });
}

export function permission_state(): string {
    if (NotificationAPI === undefined) {
        // act like notifications are blocked if they do not have access to
        // the notification API.
        return "denied";
    }
    return NotificationAPI.permission;
}

export function close_notification(message_id: number): void {
    for (const [key, notice_mem_entry] of notice_memory) {
        if (notice_mem_entry.message_id === message_id) {
            notice_mem_entry.obj.close();
            notice_mem_entry.on_close?.();
            notice_memory.delete(key);
        }
    }
}

export function granted_desktop_notifications_permission(): boolean {
    return NotificationAPI?.permission === "granted";
}

export async function request_desktop_notifications_permission(): Promise<NotificationPermission> {
    if (NotificationAPI) {
        return await NotificationAPI.requestPermission();
    }
    // Act like notifications are blocked if they do not have access to
    // the notification API.
    return "denied";
}
