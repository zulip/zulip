var tutorial = (function () {

var exports = {};
var is_running = false;
var event_handlers = {};
var deferred_work = [];

// Keep track of where we are for handling resizing.
var current_popover_info;

// We'll temporarily set stream colors for the streams we use in the demo
// tutorial messages.
var real_default_color;
var tutorial_default_color = '#76ce90';

// Each message object contains the minimal information necessary for it to be
// processed by our system for adding messages to your feed.
var today = new Date().getTime() / 1000;
var fake_messages = [
    {
        id: 1,
        content: "<p>We're working on some new screenshots for our landing page!</p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:11",
        timestamp: today,
        type: "stream",
    },
    {
        id: 2,
        content: "<p>Here's the <a href='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png' target='_blank' title='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png'>latest version</a>:<div class='message_inline_image'><a href='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png' target='_blank' title='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png'><img src='https://zulip.com/static/images/app-screenshots/zulip-desktop-windows.png'></a></div> for the Windows app -- thoughts? I'm particularly wondering whether people think the screenshot should be from Windows 7 or some other version.</p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:11",
        timestamp: today,
        type: "stream",
    },
    {
        id: 3,
        content: "<p>Looks good to me! <img alt=':+1:' class='emoji' src='/static/generated/emoji/images/emoji/+1.png' title='+1'></p>",
        is_stream: true,
        sender_full_name: "Jeff Arnold",
        sender_email: "jeff@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/dd0cf69d6d1989aa0b0d8c722f7d5840",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:16",
        timestamp: today,
        type: "stream",
    },
    {
        id: 4,
        content: "<p>Adam and I just finished a brainstorming session for the next set of integrations we want to support.</p><p><a href=''>Here</a> are our notes. I'll open tickets for the action items.</p>",
        is_stream: true,
        sender_full_name: "Jessica McKellar",
        sender_email: "jessica@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/2a1ffb4ef0b4a20c04d540a35f430cf6",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:25",
        timestamp: today,
        type: "stream",
    },
    {
        id: 5,
        content: "<p>Yay, Twitter integration. <img alt=':heart_eyes:' class='emoji' src='/static/generated/emoji/images/emoji/heart_eyes.png' title='heart eyes'></p>",
        is_stream: true,
        sender_full_name: "Leo Franchi",
        sender_email: "leo@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/4309007c980e1e8b9a2453488586482a",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:25",
        timestamp: today,
        type: "stream",
    },
    {
        id: 6,
        content: "<p>We need to add support for a few more markdown features before we can do GitHub integration.</p>",
        is_stream: true,
        sender_full_name: "Li Jing",
        sender_email: "li@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/2950c2c87fe7daaa56fd6a403ecc2ee0",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:26",
        timestamp: today,
        type: "stream",
    },
    {
        id: 7,
        content: "<p>Good point, I'll add that to the ticket.</p>",
        is_stream: true,
        sender_full_name: "Jessica McKellar",
        sender_email: "jessica@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/2a1ffb4ef0b4a20c04d540a35f430cf6",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:26",
        timestamp: today,
        type: "stream",
    },
    {
        id: 8,
        content: "<p><img alt=':clock1130:' class='emoji' src='/static/generated/emoji/images/emoji/clock1130.png' title='clock1130'> Reminder: engineering meeting in 1 hour. <img alt=':clock1130:' class='emoji' src='/static/generated/emoji/images/emoji/clock1130.png' title='clock1130'></p>",
        is_stream: true,
        sender_full_name: "Reminder Bot",
        sender_email: "reminder-bot@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/78873d7213d102dc36773046560d403a",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "weekly meeting",
        timestr: "12:30",
        timestamp: today,
        type: "stream",
    },
    {
        id: 9,
        content: "<p>Quickly brainstorming my remaining TODO list out loud for you all:</p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream",
    },
    {
        id: 10,
        content: "<p><ul><li>Redo iPhone shot</li><li>Double-check layout on iPad</li><li>Update copy for new iOS app version</li><li>Check with Android team on timeline for login redesign</li></ul></p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream",
    },
    {
        id: 11,
        content: "<p>Oops, I actually took care of the text for iOS and forgot to update the ticket -- I'll do that now.</p>",
        is_stream: true,
        sender_full_name: "Jeff Arnold",
        sender_email: "jeff@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/dd0cf69d6d1989aa0b0d8c722f7d5840",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:16",
        timestamp: today,
        type: "stream",
    },
    {
        id: 12,
        content: "<p>No problem, less work for me. <img alt=':smile:' class='emoji' src='/static/generated/emoji/images/emoji/smile.png' title='smile'></p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream",
    },
];

function disable_event_handlers() {
    $('body').css({overflow: 'hidden'}); // prevents scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        var existing_events = $._data(document, "events")[event_name];
        if (existing_events === undefined) {
            existing_events = [];
        }
        event_handlers[event_name] = existing_events;
        $._data(document, "events")[event_name] = [];
    });
}

function enable_event_handlers() {
    $('body').css({overflow: 'auto'}); // enables scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        $._data(document, "events")[event_name] = event_handlers[event_name];
    });
}

function set_tutorial_status(status, callback) {
    return channel.post({
        url:      '/json/tutorial_status',
        data:     {status: JSON.stringify(status)},
        success:  callback,
    });
}

exports.is_running = function () {
    return is_running;
};

exports.defer = function (callback) {
    deferred_work.push(callback);
};

function update_popover_info(popover_func) {
    current_popover_info = popover_func;
}

function finale(skip) {
    var finale_modal = $("#tutorial-finale");
    if (skip) {
        finale_modal.modal("hide");
        $(".screen").css({opacity: 0.0, width: 0, height: 0});
    } else {
        $(".screen").css({opacity: 0.0});
        finale_modal.css("z-index", 20001);
        finale_modal.modal("show");

        $("#tutorial-get-started").click(function () {
            finale_modal.modal("hide");
            $(".screen").css({opacity: 0.0, width: 0, height: 0});
        }).focus();
    }

    // Restore your actual stream colors and rerender to display any
    // messages received during the tutorial.
    set_tutorial_status("finished");
    is_running = false;
    current_msg_list.clear();
    update_popover_info(undefined);
    // Force a check on new events before we re-render the message list.
    server_events.force_get_events();
    stream_color.default_color = real_default_color;
    $('#first_run_message').show();
    current_msg_list.rerender();
    enable_event_handlers();
    _.each(deferred_work, function (callback) {
        callback();
    });
    deferred_work = [];

    var sender_bot = "welcome-bot@zulip.com";
    narrow.by('pm-with', sender_bot, {select_first_unread: true, trigger: 'sidebar'});
    compose_actions.cancel();
}

exports.start = function () {
    if (overlays.is_active()) {
        ui_util.change_tab_to('#home');
    }
    narrow.deactivate();

    // Set temporarly colors for the streams used in the tutorial.
    real_default_color = stream_color.default_color;
    stream_color.default_color = tutorial_default_color;
    // Add the fake messages to the feed and get started.
    current_msg_list.add_and_rerender(fake_messages);
    disable_event_handlers();
    is_running = true;
    set_tutorial_status("started");
    finale(true);
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
    $(window).resize($.debounce(100, function () {
        if (current_popover_info !== undefined) {
            current_popover_info();
        }
    }));
};

return exports;
}());
if (typeof module !== 'undefined') {
    module.exports = tutorial;
}
