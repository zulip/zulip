var tutorial = (function () {

var exports = {};
var is_running = false;
var event_handlers = {};
var deferred_work = [];

// We'll temporarily set stream colors for the streams we use in the demo
// tutorial messages.
var real_stream_info;
var tutorial_stream_info = Dict.from({"engineering": {"color": "#76ce90"}});

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
        type: "stream"
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
        type: "stream"
    },
    {
        id: 3,
        content: "<p>Looks good to me! <img alt=':+1:' class='emoji' src='static/third/gemoji/images/emoji/+1.png' title=':+1:'></p>",
        is_stream: true,
        sender_full_name: "Jeff Arnold",
        sender_email: "jeff@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/dd0cf69d6d1989aa0b0d8c722f7d5840",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:16",
        timestamp: today,
        type: "stream"
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
        type: "stream"
    },
    {
        id: 5,
        content: "<p>Yay, Twitter integration. <img alt=':heart_eyes:' class='emoji' src='static/third/gemoji/images/emoji/heart_eyes.png' title=':heart_eyes:'></p>",
        is_stream: true,
        sender_full_name: "Leo Franchi",
        sender_email: "leo@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/4309007c980e1e8b9a2453488586482a",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "integrations",
        timestr: "12:25",
        timestamp: today,
        type: "stream"
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
        type: "stream"
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
        type: "stream"
    },
    {
        id: 8,
        content: "<p><img alt=':clock1130:' class='emoji' src='static/third/gemoji/images/emoji/clock1130.png' title=':clock1130:'> Reminder: engineering meeting in 1 hour. <img alt=':clock1130:' class='emoji' src='static/third/gemoji/images/emoji/clock1130.png' title=':clock1130:'></p>",
        is_stream: true,
        sender_full_name: "Reminder Bot",
        sender_email: "reminder-bot@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/78873d7213d102dc36773046560d403a",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "weekly meeting",
        timestr: "12:30",
        timestamp: today,
        type: "stream"
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
        type: "stream"
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
        type: "stream"
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
        type: "stream"
    },
    {
        id: 12,
        content: "<p>No problem, less work for me. <img alt=':smile:' class='emoji' src='static/third/gemoji/images/emoji/smile.png' title=':smile:'></p>",
        is_stream: true,
        sender_full_name: "Abbie Patel",
        sender_email: "abbie@zulip.com",
        avatar_url: "https://secure.gravatar.com/avatar/5a8d2b3836d546d523f460924a8a9973",
        display_recipient: "engineering",
        stream: "engineering",
        subject: "screenshots",
        timestr: "12:32",
        timestamp: today,
        type: "stream"
    }
];

function send_delayed_stream_message(stream, topic, content, delay) {
    setTimeout(function () {
        $.ajax({
            dataType: 'json',
            url: '/json/tutorial_send_message',
            type: 'POST',
            data: {'type': 'stream',
                   'recipient': stream,
                   'topic': topic,
                   'content': content}
        });
    }, delay * 1000); // delay is in seconds.
}

function hide_app_alert() {
    $('#alert-bar-container').slideUp(100);
}

function show_app_alert(contents) {
    $('#custom-alert-bar-content').html(contents);
    $('#alert-bar-container').show();
    $('#alert-bar-container .close-alert-icon').expectOne().click(hide_app_alert);
}

function disable_event_handlers() {
    $('body').css({'overflow':'hidden'}); // prevents scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        var existing_events = $(document).data("events")[event_name];
        if (existing_events === undefined) {
            existing_events = [];
        }
        event_handlers[event_name] = existing_events;
        $(document).data("events")[event_name] = [];
    });
}

function enable_event_handlers() {
    $('body').css({'overflow':'auto'}); // enables scrolling the feed
    _.each(["keydown", "keyup", "keypress", "scroll"], function (event_name) {
        $(document).data("events")[event_name] = event_handlers[event_name];
    });
}

function set_tutorial_status(status, callback) {
    return channel.post({
        url:      '/json/tutorial_status',
        data:     {status: status},
        success:  callback
    });
}

exports.is_running = function () {
    return is_running;
};

function box(x, y, width, height) {
    // Blanket everything ouside the box defined by the parameters in a
    // translucent black screen, and cover the box itself with a clear screen so
    // nothing in it is clickable.
    //
    // x and y are the coordinates for hte upper-left corner of the box.

    var doc_width = $(document).width();
    var doc_height = $(document).height();

    $("#top-screen").css({opacity: 0.7, width: doc_width, height: y});
    $("#bottom-screen").offset({top: y + height, left: 0});
    $("#bottom-screen").css({opacity: 0.7, width: doc_width, height: doc_height});
    $("#left-screen").offset({top: y, left: 0});
    $("#left-screen").css({opacity: 0.7, width: x, height: height});
    $("#right-screen").offset({top: y, left: x + width});
    $("#right-screen").css({opacity: 0.7, width: x, height: height});
    $("#clear-screen").css({opacity: 0.0, width: doc_width, height: doc_height});
}

function messages_in_viewport() {
    var vp = viewport.message_viewport_info();
    var top = vp.visible_top;
    var height = vp.visible_height;
    var last_row = rows.last_visible();

    return $.merge(last_row, last_row.prevAll()).filter(function (idx, row) {
        var row_offset = $(row).offset();
        return (row_offset.top > top && row_offset.top < top + height);
    });
}

function small_window() {
    return !$("#left-sidebar").is(":visible");
}

function maybe_tweak_placement(placement) {
    // If viewed on a small screen, move popovers on the left to the center so
    // they won't be cut off.

    if (!small_window()) {
        return placement;
    }

    if (placement === "left") {
        return "bottom";
    }

    if (placement === "bottom") {
        return "right";
    }
}

function create_and_show_popover(target_div, placement, title, content_template) {
    target_div.popover({
        placement: placement,
        title: templates.render("tutorial_title", {title: title,
                                                   placement: placement}),
        content: templates.render(content_template, {placement: placement}),
        trigger: "manual"
    });
    target_div.popover("show");

    $(".popover").css("z-index", 20001);
    $(".popover-title").addClass("popover-" + placement);
}

exports.defer = function (callback) {
    deferred_work.push(callback);
};

function finale() {
    var finale_modal = $("#tutorial-finale");
    $(".screen").css({opacity: 0.0});
    finale_modal.css("z-index", 20001);
    finale_modal.modal("show");

    $("#tutorial-get-started").click(function () {
        finale_modal.modal("hide");
        $(".screen").css({opacity: 0.0, width: 0, height: 0});
    }).focus();

    // Restore your actual stream colors and rerender to display any
    // messages received during the tutorial.
    set_tutorial_status("finished");
    is_running = false;
    current_msg_list.clear();
    // Force a check on new events before we re-render the message list.
    force_get_updates();
    stream_data.set_stream_info(real_stream_info);
    util.show_first_run_message();
    current_msg_list.rerender();
    enable_event_handlers();
    _.each(deferred_work, function (callback) {
        callback();
    });
    deferred_work = [];

    var alert_contents;

    if (page_params.prompt_for_invites) {
        alert_contents = "<i class='icon-vector-heart alert-icon'></i>It's lonely in here! <a href='#invite-user' data-toggle='modal'>Invite some coworkers</a>.";
    } else {
        alert_contents = "<i class='icon-vector-desktop alert-icon'></i>What's better than Zulip in your browser? The <a href='/apps' target='_blank'>Zulip desktop app</a>!";
    }
    show_app_alert(alert_contents);

    // We start you in a narrow so it's not overwhelming.
    if (stream_data.in_home_view(page_params.notifications_stream)) {
        narrow.activate([["stream", page_params.notifications_stream]]);
    }

    if (page_params.first_in_realm) {
        // 'engineering' is the best possible stream since we used it in the
        // tutorial, but fall back to something else if we have to.
        var work_stream;
        if (stream_data.in_home_view("engineering")) {
            work_stream = "engineering";
        } else {
            work_stream = _.find(stream_data.home_view_stream_names(),
                                 function (stream_name) {
                return (stream_name !== "social") && (stream_name !== page_params.notifications_stream);
            });
        }

        if (work_stream !== undefined) {
            send_delayed_stream_message(work_stream, "projects", "This is a message on stream **" + work_stream + "** with the topic **projects**. Practice sending sending some messages here, or creating a new topic.", 10);
            send_delayed_stream_message(work_stream, "projects", "You might also enjoy:\n* Our lightweight formatting\n* emoji :thumbsup:\n* Our [desktop and mobile apps](/apps)", 15);
        }

        if (stream_data.in_home_view("social")) {
            send_delayed_stream_message("social", "cute animals", "This is a message on stream **social** with the topic **cute animals**. Try uploading or pasting in some pictures. Here's a [guinea pig](https://humbug-user-uploads.s3.amazonaws.com/byqgM1qjol1mzje_KzeNRT5F/guinea.jpg) to get you started:", 25);
        }
    }
}

function reply() {
    var spotlight_message = rows.first_visible().prev(".recipient_row");
    create_and_show_popover(spotlight_message, maybe_tweak_placement("left"),
                            "Replying", "tutorial_reply");

    var my_popover = $("#tutorial-reply").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-reply-next").click(function () {
        spotlight_message.popover("destroy");
        finale();
    }).focus();
}

function home() {
    var spotlight_message = rows.first_visible().prev(".recipient_row");
    var x = spotlight_message.offset().left;
    var y = spotlight_message.offset().top;
    var height = 0;
    _.each(messages_in_viewport(), function (row) {
        height += $(row).height();
    });

    box(x, y, spotlight_message.width(), height);
    create_and_show_popover(spotlight_message, maybe_tweak_placement("left"),
                            "Narrowing", "tutorial_home");

    var my_popover = $("#tutorial-home").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-home-next").click(function () {
        spotlight_message.popover("destroy");
        reply();
    }).focus();
}

function subject() {
    var spotlight_message = rows.first_visible();
    var bar = spotlight_message.prev(".recipient_row");
    var placement = maybe_tweak_placement("bottom");
    create_and_show_popover(bar, placement, "Topics", "tutorial_subject");

    var my_popover = $("#tutorial-subject").closest(".popover");
    if (placement === "bottom") { // Wider screen, popover is on bottom.
        my_popover.offset({left: bar.offset().left + 140 - my_popover.width() / 2});
    } else {
        my_popover.offset({left: bar.offset().left + 194});
    }

    $("#tutorial-subject-next").click(function () {
        bar.popover("destroy");
        home();
    }).focus();
}

function stream() {
    var bar = rows.first_visible().prev(".recipient_row");
    var placement = maybe_tweak_placement("bottom");
    create_and_show_popover(bar, placement, "Streams", "tutorial_stream");

    var my_popover = $("#tutorial-stream").closest(".popover");
    if (placement === "bottom") { // Wider screen, popover is on bottom.
        my_popover.offset({left: bar.offset().left + 50 - my_popover.width() / 2});
    } else { // Smaller screen, popover is to the right of the stream label.
        my_popover.offset({left: bar.offset().left + 98});
    }

    $("#tutorial-stream-next").click(function () {
        bar.popover("destroy");
        subject();
    }).focus();
}

function welcome() {
    // Grey out everything.
    $('#top-screen').css({opacity: 0.7, width: $(document).width(),
                          height: $(document).height()});

    var spotlight_message = rows.first_visible();
    var bar = spotlight_message.prev(".recipient_row");
    var x = bar.offset().left;
    var y = bar.offset().top;
    var message_height = bar.height() + spotlight_message.height();
    var message_width = bar.width();

    box(x, y, message_width, message_height);
    create_and_show_popover(bar, maybe_tweak_placement("left"), "Welcome",
                            "tutorial_message");

    var my_popover = $("#tutorial-message").closest(".popover");
    my_popover.offset({left: my_popover.offset().left - 10});

    $("#tutorial-message-next").click(function () {
        bar.popover("destroy");
        stream();
    }).focus();
}

exports.start = function () {
    if (ui.home_tab_obscured()) {
        ui.change_tab_to('#home');
    }
    narrow.deactivate();

    // Set temporarly colors for the streams used in the tutorial.
    real_stream_info = stream_data.get_stream_info();
    stream_data.set_stream_info(tutorial_stream_info);
    // Add the fake messages to the feed and get started.
    current_msg_list.add_and_rerender(fake_messages);
    disable_event_handlers();
    is_running = true;
    set_tutorial_status("started");
    welcome();
};

exports.initialize = function () {
    if (page_params.needs_tutorial) {
        exports.start();
    }
};

return exports;
}());
