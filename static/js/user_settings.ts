type UserSettingsType = {
    color_scheme: number;
    enable_desktop_notifications: boolean;
    enable_offline_push_notifications: boolean;
    enable_offline_email_notifications: boolean;
    enable_sounds: boolean;
    enable_stream_audible_notifications: boolean;
    enable_stream_desktop_notifications: boolean;
    enable_stream_email_notifications: boolean;
    enable_stream_push_notifications: boolean;
    twenty_four_hour_time: boolean;
    wildcard_mentions_notify: boolean;
};

export let user_settings = {} as UserSettingsType;

export function initialize_user_settings(params: Record<string, UserSettingsType>): void {
    user_settings = params.user_settings;
}
