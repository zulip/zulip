import $ from "jquery";

import type {NotificationData} from "./electron_bridge";
import type {Message} from "./message_store";

export type NoticeMemEntry = {
    obj: ElectronBridgeNotification | Notification;
    msg_count: number;
    message_id: number;
};

export const notice_memory: Map<string, NoticeMemEntry> = new Map();

export let NotificationAPI: typeof ElectronBridgeNotification | typeof window.Notification;

export function set_notification_api(
    n: typeof ElectronBridgeNotification | typeof window.Notification,
): void {
    NotificationAPI = n;
}

class ElectronBridgeNotification extends EventTarget {
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
        let notification_data: NotificationData = {
            title: "",
            dir: "auto",
            lang: "",
            body: "",
            tag: "",
            icon: "",
            data: "",
            close() {},
        };
        if (window.electron_bridge && window.electron_bridge.new_notification) {
            notification_data = window.electron_bridge.new_notification(
                title,
                options,
                (type, eventInit) => this.dispatchEvent(new Event(type, eventInit)),
            );
        }
        this.title = notification_data.title;
        this.dir = notification_data.dir;
        this.lang = notification_data.lang;
        this.body = notification_data.body;
        this.tag = notification_data.tag;
        this.icon = notification_data.icon;
        this.data = notification_data.data;
        this.close = (): void => {
            notification_data.close();
        };
    }

    static get permission(): NotificationPermission {
        return Notification.permission;
    }

    static async requestPermission(
        callback: NotificationPermissionCallback | undefined = undefined,
    ): Promise<NotificationPermission> {
        if (callback) {
            callback(await Promise.resolve(Notification.permission));
        }
        return Notification.permission;
    }
}

if (window.electron_bridge && window.electron_bridge.new_notification) {
    NotificationAPI = ElectronBridgeNotification;
} else if (window.Notification) {
    NotificationAPI = window.Notification;
}

export function get_notifications(): Map<string, NoticeMemEntry> {
    return notice_memory;
}

export function initialize(): void {
    $(window).on("focus", () => {
        for (const notice_mem_entry of notice_memory.values()) {
            notice_mem_entry.obj.close();
        }
        notice_memory.clear();
    });
}

export function permission_state(): NotificationPermission {
    if (NotificationAPI === undefined) {
        // act like notifications are blocked if they do not have access to
        // the notification API.
        return "denied";
    }
    return NotificationAPI.permission;
}

export function close_notification(message: Message): void {
    for (const [key, notice_mem_entry] of notice_memory) {
        if (notice_mem_entry.message_id === message.id) {
            notice_mem_entry.obj.close();
            notice_memory.delete(key);
        }
    }
}

export function granted_desktop_notifications_permission(): boolean {
    return NotificationAPI && NotificationAPI.permission === "granted";
}

export function request_desktop_notifications_permission(): void {
    if (NotificationAPI) {
        void NotificationAPI.requestPermission();
    }
}
