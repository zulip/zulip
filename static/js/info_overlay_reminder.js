import $ from "jquery";

import render_reminder_notifications from "../templates/reminder_notifications.hbs";
import render_topic_reminder_list_item from "../templates/topic_reminder_list_item.hbs";

import * as browser_history from "./browser_history";
import * as components from "./components";
import {$t, $t_html} from "./i18n";
import * as keydown_util from "./keydown_util";
import * as overlays from "./overlays";
import * as ui from "./ui";
import * as ListWidget from "./list_widget";
import * as hash_util from "./hash_util";

// Make it explicit that our toggler is undefined until
// set_up_toggler is called.
export let toggler;


export function set_up_toggler(muted_topics) {
    const $reminder_notifications = $(render_reminder_notifications());
    $(".informational-overlays-reminder .overlay-reminder-body").append($reminder_notifications);

    render_topic_reminder_list(muted_topics);

    const opts = {
        selected: 0,
        child_wants_focus: true,
        values: [
            {label: $t({defaultMessage: "Upcoming unmutes ..."}), key: "reminder-notifications"},
        ],
        callback(name, key) {
            $(".overlay-reminder-modal").hide();
            $(`#${CSS.escape(key)}`).show();
            ui.get_scroll_element($(`#${CSS.escape(key)}`).find(".modal-body"));
        },
    };

    toggler = components.toggle(opts);
    const elem = toggler.get();
    elem.addClass("large allow-overflow");

    const modals = opts.values.map((item) => {
        const key = item.key;
        const modal = $(`#${CSS.escape(key)}`).find(".modal-body");
        return modal;
    });

    for (const modal of modals) {
        ui.get_scroll_element(modal).prop("tabindex", 0);
        keydown_util.handle({
            elem: modal,
            handlers: {
                ArrowLeft: toggler.maybe_go_left,
                ArrowRight: toggler.maybe_go_right,
            },
        });
    }

    $(".informational-overlays-reminder .overlay-reminder-tabs").append(elem);
}

export function show(target) {
    if (!toggler) {
        set_up_toggler(target);
    }

    const overlay = $(".informational-overlays-reminder");

    if (target.length > 0 && !overlay.hasClass("show")) {
        overlays.open_overlay({
            name: "informationalOverlaysReminder",
            overlay,
            on_close() {
                browser_history.exit_overlay();
            },
        });
    }

    if (target) {
        toggler.goto(target);
    }
}

function format_topic_reminder_list_item(topic) {
    let date = null;
    let date_formatted = null;

    if (topic.muted_datetime != null)
        date = new Date(topic.muted_datetime);
        
        let month = '';
        
        switch(date.getMonth() + 1) {
            case 1: month = "January";
                break;
            case 2: month = "February";
                break;
            case 3: month = "March";
                break;
            case 4: month = "April";
                break;
            case 5: month = "May";
                break;
            case 6: month = "June"; 
                break;
            case 7: month = "July";
                break;
            case 8: month = "August";
                break;
            case 9: month = "September";
                break;
            case 10: month = "October";
                break;
            case 11: month = "November";
                break;
            case 12: month = "December";
                break;
        }
        
        let minutes = date.getMinutes();
        if(minutes < 10)
            date_formatted = date.getDate() + " " + month + " " + date.getHours() + ":0" + date.getMinutes();
        else
            date_formatted = date.getDate() + " " + month + " " + date.getHours() + ":" + date.getMinutes();

    return render_topic_reminder_list_item({
        topic_name: topic.topic,
        stream_name: topic.stream_name,
        stream_id: topic.stream_id,
        muted_datetime: date_formatted,
        remind_datetime: topic.remind_datetime,
        topic_url: hash_util.by_stream_topic_uri(topic.stream_id, topic.topic),
        stream_url: hash_util.by_stream_uri(topic.stream_id),
    });
}

function render_topic_reminder_list(topics) {
    const container = $(".informational-overlays-reminder .remind-topics-list");
    container.empty();

    ListWidget.create(container, topics, {
        modifier(item) {
            return format_topic_reminder_list_item(item);
        },
        simplebar_container: $(".informational-overlays-reminder .modal-body"),
    });
}