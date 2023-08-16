import * as compose_fade_helper from "./compose_fade_helper";
import * as people from "./people";

export type Configuration = {
    get_user_id(li: JQuery<HTMLElement>): number;
    unfade(li: JQuery<HTMLElement>): void;
    fade(li: JQuery<HTMLElement>): void;
};

function update_user_row_when_fading(li: JQuery<HTMLElement>, conf: Configuration): void {
    const user_id = conf.get_user_id(li);
    const would_receive = compose_fade_helper.would_receive_message(user_id);

    if (would_receive || people.is_my_user_id(user_id)) {
        conf.unfade(li);
    } else {
        conf.fade(li);
    }
}

export function fade_users(items: JQuery<HTMLElement>[], conf: Configuration): void {
    for (const li of items) {
        update_user_row_when_fading(li, conf);
    }
}

export function display_users_normally(items: JQuery<HTMLElement>[], conf: Configuration): void {
    for (const li of items) {
        conf.unfade(li);
    }
}

export function update_user_info(items: JQuery<HTMLElement>[], conf: Configuration): void {
    if (compose_fade_helper.want_normal_display()) {
        display_users_normally(items, conf);
    } else {
        fade_users(items, conf);
    }
}
