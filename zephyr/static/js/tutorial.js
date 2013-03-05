var tutorial = (function () {

var exports = {};

function go(fn, arg) {
    return function() { return fn(arg); };
}

function go2(fn, arg1, arg2) {
    return function() { return fn(arg1, arg2); };
}

// Inspired by
// http://www.intridea.com/blog/2011/2/8/fun-with-jquery-deferred
//
// Basically, we make a new Deferred object that gets resolved
// when our setTimeout returns. Which means we effectively sleep
// for some amount of time, but can also chain it with .thens
// with our other deferred objects.
function sleep(time_in_ms) {
    return $.Deferred(function(deferred) {
        setTimeout(deferred.resolve, time_in_ms);
    });
}

function pm(message) {
    return $.ajax({
        dataType: 'json',
        url: '/json/tutorial_send_message',
        type: 'POST',
        data: {'type': 'private',
               'content': message}
    });
}

function stream_message(subject, message) {
    return $.ajax({
        dataType: 'json',
        url: '/json/tutorial_send_message',
        type: 'POST',
        data: {'type': 'stream',
               'subject': subject,
               'content': message}
    });
}

// populated later -- should be e.g. tutorial-wdaher
var my_tutorial_stream;

function stream_to_me(message) {
    return message.type === 'stream' && message.to === my_tutorial_stream;
}

function pm_to_me(message) {
    return message.type === 'private' && message.to[0] === 'humbug+tutorial@humbughq.com';
}

function any_message_to_me(message) {
    return pm_to_me(message) || stream_to_me(message);
}

var received_messages = [];
exports.message_was_sent = function(message) {
    var trimmed_content = message.content.trim().toLowerCase();
    if (any_message_to_me(message) &&
        (trimmed_content === 'exit' || trimmed_content === 'stop')) {
        sleep(1000).then(go(pm, "OK, cool, we'll stop the tutorial here. If you have any questions, you can always email support@humbughq.com!"));
        exports.stop();
        return;
    }
    received_messages.push(message);
};

function wait_for_message(time_to_wait_sec, condition) {
    var POLL_INTERVAL_MS = 500;
    received_messages = [];
    return $.Deferred(function (deferred) {
        var numCalls = 0;
        var intervalId = setInterval(function () {
            numCalls += 1;
            if (numCalls > time_to_wait_sec * 1000 / POLL_INTERVAL_MS) {
                clearInterval(intervalId);
                // We didn't get an answer; end the tutorial.
                deferred.fail();
            }

            if (received_messages.length > 0) {
                var success = true;
                if (condition) {
                    success = false;
                    $.each(received_messages, function (idx, val) {
                        if (condition(val)) success = true;
                    });
                }

                received_messages = [];
                if (success) {
                    deferred.resolve();
                    clearInterval(intervalId);
                }
            }

        }, POLL_INTERVAL_MS);
    });
}

var script = [];

function make_script() {
    my_tutorial_stream = 'tutorial-' + email.split('@')[0];

    // Try to guess at one of your main streams.
    // This is problematic because it might end up being 'commits' or something.
    var main_stream_name = domain.split('.')[0];
    var my_streams = subs.subscribed_streams();

    if (my_streams.length <= 2) {
      // What?? Add some more examples, I guess.
      if ($.inArray('social', my_streams) === -1) my_streams.push('social');
      if ($.inArray('commits', my_streams) === -1) my_streams.push('commits');
      if ($.inArray('jenkins', my_streams) === -1) my_streams.push('jenkins');
    }
    if ($.inArray(main_stream_name, my_streams) === -1) {
      main_stream_name = my_streams[0];
    }
    // Special hack for CUSTOMER18 -- if there's a stream named customer18stream1, well, then
    // that's definitely the one to pick
    if ($.inArray('customer18stream1', my_streams) !== -1) {
        main_stream_name = 'customer18stream1';
    }

    script = [
  go(sleep, 1000), // The first message seems to sometimes get eaten in Chrome otherwise.
  go2(stream_message, "tutorial", "Hello, " + fullname + "!"),
  go(sleep, 2000),
  go2(stream_message, "tutorial", "Welcome to Humbug!"),
  go(sleep, 2000),
  go2(stream_message, "tutorial", "I'm the Humbug tutorial bot and I'll be showing you around."),
  go(sleep, 2000),
  go2(stream_message, "tutorial",'At any time, you can stop this tutorial by replying to me with the word "exit".'),
  go(sleep, 3000),
  go2(stream_message, "tutorial", "Why don't you **reply to this message and say hello?** "
    + "(Click on a message to reply.)"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial",'Great, thanks! After you\'ve typed your reply, you can send it by clicking "Send", but you can also send from the keyboard by pressing `Tab` and then `Enter`.'),
  go(sleep, 4000),
  go2(stream_message, "tutorial", "Give it a shot!\n**Reply to me again, and use Tab, then Enter to send it.**"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial", "Nice work. In Humbug, time flows down. Your new messages will always appear at the very bottom of the screen, and we don't automatically scroll. We're always receiving messages for you -- even when you're logged out."),
  go(sleep, 6000),
  go2(stream_message, "tutorial", "By the way, right now, these messages are going to stream `" + my_tutorial_stream + "`.\n\nA stream is like a chatroom or mailing list; anyone on `" + my_tutorial_stream +"` can see and respond to these messages right now. (In this case, it's just us on this stream right now, so that no one distracts us.)"),
  go(sleep, 8000),
  go2(stream_message, "tutorial", "Every stream message has a subject associated with it. (In this case, `tutorial`). "
      + "The subject should ideally be **one word** describing the topic of the message.\n\nGood subjects: `lunch` or `humbug-test.git` or `jQuery`.\n"),
  go(sleep, 10000),
  go2(stream_message, "tutorial", "Why subjects are really powerful:\n"
      + "* They make it easy to keep track of multiple conversations\n"
      + "* When you return to your computer after being away, they let you easily skim so that you can read what you care about and ignore what you don't. (Especially great if you have remote workers!)\n"
      + "* They're lightweight (remember, one word)\n"),
  go(sleep, 8000),
  go2(stream_message, "tutorial", "I know that's a lot to take in, but once you understand the model, Humbug can be insanely productive. I'll give you a second to catch your breath, but send me a reply when you're ready to continue."),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go(pm, "Psst, Humbug also has private messages, like this one, which you can send to one or more people. No one else can see this message but us.\n\nReply to my private message to continue."),
  go2(wait_for_message, 300, pm_to_me),
  go(sleep, 1000),
  go(pm, "Nicely done. Alright, back to stream messages we go!"),
  go(sleep, 2000),
  go2(stream_message, "tutorial", "It's easy to make or join streams. If you click the gear on the top right of the page, and then pick 'Streams', you can create your own stream, join streams that other people have made, or set colors for your streams."),
  go(sleep, 4000),
  go2(stream_message, "tutorial", "Go in there now and set a color for `" + my_tutorial_stream + "`. Then come back here, and tell me when you've done so."),
  go(sleep, 5000),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  // Narrowing
  go2(stream_message, "narrowing", "Another valuable feature of Humbug is **narrowing**. Click on the word \"narrowing\" directly above this message, and tell me when you've done so."),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "narrowing", "Great! We're now only looking at messages on stream `" + my_tutorial_stream + "`, subject `narrowing`. You can tell because the background is grey, and the search bar at the top has a query in it. You can narrow on many different types of things, including:\n"
   + "* A specific stream, by clicking on the stream name\n"
   + "* A specific stream-subject pair, by clicking on the subject name (like we just did)\n"
   + "* Private messages with a specific person\n\n"
   + "Press `Esc` to get out of this narrowed view, scroll down to the bottom, and tell me when you've done so.\n"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial", "You've got a hang of the basics, so let's talk about some advanced features.\nThe first: code."),
  go(sleep, 5000),
  // Markdown
  go2(stream_message, "tutorial", "Humbug makes it easy to send syntax-highlighted code blocks. Just surround the block in three `~`s and the extension for your programming language, and you get something pretty, like this:\n\n"
    + "~~~~~ .py\n"
    + "~~~ .py\n"
    + "def foo(arg):\n"
    + "    print 'Hello'\n"
    + "~~~\n"
    + "~~~~~"),
  go(sleep, 7000),
  go2(stream_message, "tutorial", "You can also do inline preformatted text by surrounding it in `` `s. Finally, there's also more formatting help that you can see by clicking the 'Formatting' link in the new message box."),
  go(sleep, 6000),
  go2(stream_message, "tutorial", "(Tell me when you're ready to continue.)"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  go2(stream_message, "tutorial", "Great, you did it! There are a bunch of other features I'd love to tell you about that we don't have time for, but look into these later:\n"
    + "* Keyboard shortcuts (press `?` to see them)\n"
    + "* Our [API](https://humbughq.com/api)\n"
    + "* Our [integrations](https://humbughq.com/integrations) with popular services like GitHub, Jenkins, etc.\n"
    + '* Alpha mobile apps for [Android](https://play.google.com/store/apps/details?id=com.humbughq.mobile) and (by request) [iPhone](mailto:support@humbughq.com?subject=Request+for+Humbug+iPhone+app&body=Hi+Humbug,+can+you+send+me+a+link+to+the+iPhone+app+alpha?+I+have+an+iPhone+__.)'),
  go(sleep, 4000),
  go2(stream_message, "tutorial", "(Tell me when you're ready to continue.)"),
  go2(wait_for_message, 300, any_message_to_me),
  go(sleep, 1000),
  // Have them go talk to people
  go2(stream_message, "tutorial", ":white_check_mark: **Congratulations! The tutorial is now complete** :tada:\n"
      + "We've removed you from the `" + my_tutorial_stream + "` stream, since you're done.\n\n"
      + "Some things you can do from here:\n"
      + "* Send a private message to someone by clicking their name in the right sidebar\n"
      + "* Send a new stream message, or reply to an existing one\n"
      + "(One suggestion: A message to stream `" + main_stream_name +"` with subject `humbug` to let everyone know you're here!)\n"),
  function () { exports.stop(); }
    ];
}

var tutorial_running = false;

function run_tutorial(stepNumber) {
    if (stepNumber >= script.length) {
        exports.stop();
    }

    if (!tutorial_running) {
        return;
    }
    var step = script[stepNumber];
    var res = step();
    if (res) {
        res.then(function () { run_tutorial(++stepNumber); });
    } else {
        // Our last function wasn't async at all, so just proceed with the next step
        run_tutorial(++stepNumber);
    }
}

function add_to_tutorial_stream() {
    if ($.inArray(my_tutorial_stream, subs.subscribed_streams()) === -1) {
        subs.tutorial_subscribe_or_add_me_to(my_tutorial_stream);
    }
}

exports.start = function () {
    if (tutorial_running) {
        // Not more than one of these at once!
        return;
    }
    tutorial_running = true;
    add_to_tutorial_stream();
    run_tutorial(0);
};

// This technique is not actually that awesome, because it's pretty
// race-y. Let's say I start() and then stop() and then start() again;
// an async from the first start() might still be returning, and it'll
// come back and say "Oh, we're still going!" and the tutorial #1 will
// continue.
//
// Fortunately, in v1, the only real thing that initiates the tutorial
// is logging in to a fresh system, so this is mostly a non-issue;
// the rationale being that you could just scroll back up and read
// the tutorial if you still need it.
exports.stop = function () {
    if (tutorial_running) {
        subs.tutorial_unsubscribe_me_from(my_tutorial_stream);
        tutorial_running = false;
    }
};

exports.is_running = function () {
    return tutorial_running;
};

var should_autostart_tutorial = false;
exports.run_when_ready = function () {
    should_autostart_tutorial = true;
};

exports.initialize = function () {
    make_script();
    if (should_autostart_tutorial) {
        tutorial.start();
    }
};

return exports;
}());
