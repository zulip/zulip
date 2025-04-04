import $ from "jquery";
import assert from "minimalistic-assert";

import {electron_bridge} from "./electron_bridge.ts";
import type {Message} from "./message_store.ts";

type NoticeMemory = Map<
    string,
    {
        obj: Notification | ElectronBridgeNotification;
        msg_count: number;
        message_id: number;
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

export function get_notifications(): NoticeMemory {
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

export function permission_state(): string {
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
