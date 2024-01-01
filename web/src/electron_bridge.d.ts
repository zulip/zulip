export type NotificationData = {
    title: string;
    dir: NotificationDirection;
    lang: string;
    body: string;
    tag: string;
    icon: string;
    data: unknown;
    close: () => void;
};

export type ClipboardDecrypter = {
    version: number;
    key: Uint8Array;
    pasted: Promise<string>;
};

export type ElectronBridge = {
    send_event: (eventName: string | symbol, ...args: unknown[]) => boolean;
    on_event: ((
        eventName: "logout" | "show-keyboard-shortcuts" | "show-notification-settings",
        listener: () => void,
    ) => void) &
        ((
            eventName: "send_notification_reply_message",
            listener: (message_id: unknown, reply: unknown) => void,
        ) => void);
    new_notification?: (
        title: string,
        options: NotificationOptions,
        dispatch: (type: string, eventInit: EventInit) => boolean,
    ) => NotificationData;
    get_idle_on_system?: () => boolean;
    get_last_active_on_system?: () => number;
    get_send_notification_reply_message_supported?: () => boolean;
    set_send_notification_reply_message_supported?: (value: boolean) => void;
    decrypt_clipboard?: (version: number) => ClipboardDecrypter;
};

declare global {
    // eslint-disable-next-line @typescript-eslint/consistent-type-definitions
    interface Window {
        electron_bridge?: ElectronBridge;
    }
}
