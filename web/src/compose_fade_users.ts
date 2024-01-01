import * as compose_fade_helper from "./compose_fade_helper";
import * as people from "./people";

export type UserFadeConfig<T> = {
    get_user_id: (elem: T) => number;
    fade: (elem: T) => void;
    unfade: (elem: T) => void;
};

function update_user_row_when_fading<T>(item: T, conf: UserFadeConfig<T>): void {
    const user_id = conf.get_user_id(item);
    const would_receive = compose_fade_helper.would_receive_message(user_id);

    if (would_receive || people.is_my_user_id(user_id)) {
        conf.unfade(item);
    } else {
        conf.fade(item);
    }
}

export function fade_users<T>(items: T[], conf: UserFadeConfig<T>): void {
    for (const item of items) {
        update_user_row_when_fading(item, conf);
    }
}

export function display_users_normally<T>(items: T[], conf: UserFadeConfig<T>): void {
    for (const item of items) {
        conf.unfade(item);
    }
}

export function update_user_info<T>(items: T[], conf: UserFadeConfig<T>): void {
    if (compose_fade_helper.want_normal_display()) {
        display_users_normally(items, conf);
    } else {
        fade_users(items, conf);
    }
}
