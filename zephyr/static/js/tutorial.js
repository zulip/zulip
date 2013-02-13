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

function send_message(message) {
    return $.ajax({
        dataType: 'json',
        url: '/json/tutorial_send_message',
        type: 'POST',
        data: {'message': message}
    });
}

var received_messages = [];
exports.message_was_sent = function(message) {
    var trimmed_content = message.content.trim().toLowerCase();
    if (message.type === 'private'
        && (trimmed_content === 'exit' || trimmed_content === 'stop')) {
        sleep(1000).then(go(send_message, "OK, cool, we'll stop the tutorial here. If you have any questions, you can always email support@humbughq.com!"));
        exports.stop();
        return;
    }
    received_messages.push(message);
};


function pm_to_me(message) {
    return message.type === 'private' && message.to[0] === 'humbug+tutorial@humbughq.com';
}

function wait_for_message(time_to_wait_sec, condition) {
    var POLL_INTERVAL_MS = 500;
    received_messages = [];
    return $.Deferred(function (deferred) {
        var numCalls = 0;
        var intervalId = setInterval(function () {
            numCalls += 1;
            if (numCalls > time_to_wait_sec * 1000 / POLL_INTERVAL_MS) {
                clearInterval(intervalId);
                // Normally we would defer.fail here, but we want the tutorial to continue
                // regardless, so we'll resolve it.
                deferred.resolve();
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

    script = [
  go(sleep, 1000), // The first message seems to sometimes get eaten in Chrome otherwise.
  go(send_message, "Hello, " + fullname + "!"),
  go(sleep, 2000),
  go(send_message, "Welcome to Humbug!"),
  go(sleep, 2000),
  go(send_message, "I'm the Humbug tutorial bot and I'll be showing you around."),
  go(sleep, 2000),
  go(send_message, 'At any time, you can stop this tutorial by replying to me with the word "exit".'),
  go(sleep, 3000),
  go(send_message, "Why don't you **reply to me and say hello?** "
    + "(Click on this message to reply.)"),
  go2(wait_for_message, 120, pm_to_me),
  go(sleep, 1000),
  go(send_message, 'Great, thanks! After you\'ve typed your reply, you can send it by clicking "Send", but you can also send from the keyboard by pressing `Tab` and then `Enter`.'),
  go(sleep, 4000),
  go(send_message, "Give it a shot!\n**Send me a reply, and use Tab, then Enter to send it.**"),
  go2(wait_for_message, 120, pm_to_me),
  go(sleep, 1000),
  go(send_message, "Nice work. In Humbug, time flows down. Your new messages will always appear at the very bottom of the screen, and we don't automatically scroll. We're always receiving messages for you -- even when you're logged out."),
  go(sleep, 4000),
  go(send_message, "By the way, right now we are exchanging **private messages**. Private messages can go to one or more recipients, and basically are just like a normal IM."),
  go(sleep, 4000),
  go(send_message, "But Humbug also has **stream messages**. A stream is kind of like a group chatroom or a mailing list. Every stream message has two parts parts:\n"
    + "* The **stream** name: e.g. `" + my_streams[0] + "` or `" + my_streams[1] + "` or `" + my_streams[2] + "`\n"
    + "* The **subject**: typically one word describing the topic of the message (e.g. `lunch`, or `humbug-test.git` or `jQuery`)\n"),
  go(sleep, 10000),
  go(send_message, "The one-word subject is important because it lets you quickly read what you care about, and ignore what you don't. (Think of how useful email subject lines are!)"),
  go(sleep, 4000),
  go(send_message, "I know that's a lot to take in, but once you understand the model, Humbug can be really powerful. I'll give you a second to catch your breath, but send me a reply when you're ready to continue."),
  go2(wait_for_message, 180, pm_to_me),
  go(sleep, 1000),
  go(send_message, "We've started out by adding you to a few streams by default -- those appear on the left sidebar."),
  go(sleep, 2000),
  go(send_message, "Why don't you send a message to let everyone know you're out there? Click the 'New stream message' button on the left, and send a message to stream `" + main_stream_name + "`,  subject `signups`, with a message like \"Hey, I'm now on Humbug!\". (You could also press `c` to start a new message.)"),
  go2(wait_for_message, 180, function (message) {
      return message.type === 'stream' && message.subject.trim().toLowerCase() === 'signups';
  }),
  go(sleep, 1000),
  go(send_message, "Great work! Other people might reply to your message while the tutorial is running, but that's ok! Managing multiple things at once is one of the strengths of Humbug."),
  go(sleep, 3000),
  go(send_message, "It's easy to make or join streams. If you click the gear on the top right of the page, and then pick 'Streams', you can create your own stream, join streams that other people have made, or set colors for your streams."),
  go(sleep, 3000),
  go(send_message, "Go in there and set a color for `" + main_stream_name + "`. Then come back here, and tell me when you've done so."),
  go(sleep, 1000),
  //*********
  // This call is particularly interesting because unlike all the others, it isn't an async
  // call at all. But that's ok! Just wrap it in a function and return null and it will work
  // (though it will proceed with the next task immediately after executing the function)
  function() { $("#gear-menu").addClass('open'); },
  //*********
  go2(wait_for_message, 240, pm_to_me),
  go(sleep, 1000),
  go(send_message, "Great! A couple things to note about subjects:\n"
    + "* It's tempting to overthink your choice of subject. Don't.\n"
    + "* Go with your gut. Typically one word will do: `meeting`, `Python`, or `lunch`\n"
    + "* Subjects are preserved across replies, so most of the time you won't even have to think about them\n"),
  go(sleep, 8000),
  // Narrowing
  go(send_message, "Another valuable feature of Humbug is **narrowing**. Click on **You and Humbug Tutorial Bot**, scroll to the bottom, and tell me when you've done so."),
  go2(wait_for_message, 180, pm_to_me),
  go(sleep, 1000),
  go(send_message, "Great! We're now looking only at messages between us. You can tell because the background is grey, and the search bar at the top has a query in it. You can narrow on many different types of things, including:\n"
   + "* A specific stream, by clicking on the stream name, or\n"
   + "* A specific stream-subject pair, by clicking on the subject name\n\n"
   + "Press `Esc` to get out of this narrowed view, and tell me when you've done so.\n"),
  go2(wait_for_message, 180, pm_to_me),
  go(sleep, 1000),
  go(send_message, "Okay, we're almost done -- I just want to quickly mention two more things. The first: code blocks."),
  go(sleep, 3000),
  // Markdown
  go(send_message, "Humbug makes it really easy to send syntax-highlighted code blocks. Just start the block with three `~`s and the extension for your programming language, like this:\n\n"
    + "~~~~~\n"
    + "~~~ .py\n"
    + "def fn(arg):\n"
    + "    print 'Hello'\n"
    + "~~~\n"
    + "~~~~~"),
  go(sleep, 4000),
  go(send_message, "Go ahead and try typing in that exact text, in a response to me."),
  go2(wait_for_message, 300, function (message) {
    return message.type === 'private' && message.to[0] === 'humbug+tutorial@humbughq.com' &&
        message.content.trim().toLowerCase().indexOf("~~~") !== -1;
  }),
  go(sleep, 1000),
  go(send_message, "Great, you did it! There are a bunch of other features I'd love to tell you about that we don't have time for, but experiment with:\n"
    + "* Keyboard shortcuts (press `?` to see them)\n"
    + "* More formatting support (there's a 'Formatting' link in the composebox, above the Send button)\n"
    + "  (In particular, you can format one line of code by surrounding it in `` `s)\n"
    + "* The search bar at the top, and\n"
    + "* Our [API](https://humbughq.com/api) and [Integrations](https://humbughq.com/integrations)"),
  go(sleep, 12000),
  // Have them go talk to people
  go(send_message, "**Congratulations! The tutorial is now complete**. Enjoy Humbug!"),
  go(sleep, 3000),
  go(send_message, "Some things you can do from here:\n"
    + "* Send a private message to someone by clicking their name in the left sidebar\n"
    + "* Send a new stream message, or reply to an existing one\n"
    + "(One suggestion: A message to stream `" + main_stream_name +"` with subject `today` about what you will be working on today).\n"
    + "* Invite your coworkers (from the gear menu)\n")
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


exports.start = function () {
    if (tutorial_running) {
        // Not more than one of these at once!
        return;
    }
    tutorial_running = true;
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
    tutorial_running = false;
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
