"use strict";

// Global variables, categorized by place of definition.
var globals =
    // Third-party libraries
      ' $ jQuery Spinner Handlebars XDate'

    // index.html
    + ' initial_pointer email stream_list people_list have_initial_messages'
    + ' fullname desktop_notifications_enabled enter_sends domain poll_timeout'

    // common.js
    + ' status_classes'

    // setup.js
    + ' templates csrf_token'

    // Modules, defined in their respective files.
    + ' compose rows hotkeys narrow reload notifications_bar search subs'
    + ' composebox_typeahead typeahead_helper notifications hashchange'
    + ' invite ui util activity timerender MessageList'

    // colorspace.js
    + ' colorspace'

    // tutorial.js
    + ' tutorial'

    // zephyr.js
    + ' all_msg_list home_msg_list narrowed_msg_list current_msg_list get_updates_params'
    + ' add_messages'
    + ' subject_dict people_dict'
    + ' keep_pointer_in_view move_pointer_at_page_top_and_bottom'
    + ' respond_to_message recenter_view'
    + ' scroll_to_selected disable_pointer_movement get_private_message_recipient'
    + ' load_old_messages'
    + ' at_top_of_viewport at_bottom_of_viewport'
    + ' viewport'
    + ' load_more_messages reset_load_more_status have_scrolled_away_from_top'
    + ' home_unread_messages'
    + ' maybe_scroll_to_selected recenter_pointer_on_display suppress_scroll_pointer_update'
    + ' process_unread_counts message_range message_in_table'
    ;


var options = {
    vars:     true,  // Allow multiple 'var' per function
    sloppy:   true,  // Don't require "use strict"
    white:    true,  // Lenient whitespace rules
    plusplus: true,  // Allow increment/decrement operators
    regexp:   true,  // Allow . and [^...] in regular expressions
    todo:     true,  // Allow "TODO" comments.
    newcap:   true,  // Don't assume that capitalized functions are
                     // constructors (and the converse)
    nomen:    true,  // Tolerate underscore at the beginning of a name
    stupid:   true   // Allow synchronous methods
};


// For each error.raw message, we can return 'true' to ignore
// the error.
var exceptions = {
    "Expected '{a}' and instead saw '{b}'." : function (error) {
        // We allow single-statement 'if' with no brace.
        // This exception might be overly broad but oh well.
        return (error.a === '{');
    },

    "Unexpected 'else' after 'return'." : function () {
        return true;
    },

    "Don't make functions within a loop." : function () {
        return true;
    }
};


var fs     = require('fs');
var path   = require('path');
var JSLINT = require(path.join(__dirname, 'jslint')).JSLINT;

var cwd    = process.cwd();

var exit_code = 0;
var i;

// Drop 'node' and the script name from args.
for (i=0; i<2; i++) {
    process.argv.shift();
}

process.argv.forEach(function (filepath) {
    var contents = fs.readFileSync(filepath, 'utf8');
    var messages = [];

    // We mutate 'options' so be sure to clear everything.
    if (filepath.indexOf('zephyr/static/js/') !== -1) {
        // Frontend browser code
        options.browser = true;
        options.node    = false;
        options.predef  = globals.split(/\s+/);
    } else {
        // Backend code for Node.js
        options.browser = false;
        options.node    = true;

        if (filepath.indexOf('zephyr/tests/frontend/') !== -1) {
            // Include '$' because we use jQuery inside casper.evaluate
            options.predef = ['casper', '$'];
        } else {
            options.predef = [];
        }
    }

    if (!JSLINT(contents, options)) {
        JSLINT.errors.forEach(function (error) {
            if (error === null) {
                // JSLint stopping error
                messages.push('          (JSLint giving up)');
                return;
            }

            var exn = exceptions[error.raw];
            if (exn && exn(error)) {
                // Ignore this error.
                return;
            }

            // NB: this will break on a 10,000 line file
            var line = ('    ' + error.line).slice(-4);

            messages.push('    ' + line + '  ' + error.reason);
        });

        if (messages.length > 0) {
            exit_code = 1;

            console.log(path.relative(cwd, filepath));

            // Something very wacky happens if we do
            // .forEach(console.log) directly.
            messages.forEach(function (msg) {
                console.log(msg);
            });

            console.log('');
        }
    }
});

process.exit(exit_code);
