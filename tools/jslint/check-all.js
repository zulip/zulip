"use strict";

// Global variables, categorized by place of definition.
var globals =
    // Third-party libraries
      ' $ jQuery Spinner Handlebars XDate'

    // index.html
    + ' initial_pointer email stream_list people_list have_initial_messages'
    + ' desktop_notifications_enabled domain'

    // common.js
    + ' status_classes'

    // compose.js
    + ' compose'

    // rows.js
    + ' rows'

    // hotkey.js
    + ' hotkeys'

    // narrow.js
    + ' narrow'

    // reload.js
    + ' reload'

    // search.js
    + ' search'

    // setup.js
    + ' loading_spinner templates csrf_token'

    // subs.js
    + ' subs'

    // composebox_typeahead.js
    + ' composebox_typeahead'

    // typeahead_helper.js
    + ' typeahead_helper'

    // notifications.js
    + ' notifications'

    // ui.js
    + ' ui'

    // zephyr.js
    + ' message_array message_dict get_updates_params'
    + ' clear_table add_to_table add_messages'
    + ' subject_dict same_stream_and_subject'
    + ' keep_pointer_in_view move_pointer_at_page_top_and_bottom'
    + ' respond_to_message'
    + ' select_message select_message_by_id'
    + ' scroll_to_selected disable_pointer_movement'
    + ' load_old_messages'
    + ' selected_message selected_message_id'
    + ' at_top_of_viewport at_bottom_of_viewport'
    + ' viewport'
    + ' load_more_messages reset_load_more_status have_scrolled_away_from_top'
    ;


var jslint_options = {
    browser:  true,  // Assume browser environment
    vars:     true,  // Allow multiple 'var' per function
    sloppy:   true,  // Don't require "use strict"
    white:    true,  // Lenient whitespace rules
    plusplus: true,  // Allow increment/decrement operators
    regexp:   true,  // Allow . and [^...] in regular expressions
    todo:     true,  // Allow "TODO" comments.

    predef: globals.split(/\s+/)
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
    }
};


var fs     = require('fs');
var path   = require('path');
var JSLINT = require(path.join(__dirname, 'jslint')).JSLINT;

var cwd    = process.cwd();
var js_dir = fs.realpathSync(path.join(__dirname, '../../zephyr/static/js'));

var exit_code = 0;

fs.readdirSync(js_dir).forEach(function (filename) {
    if (filename.slice('-3') !== '.js')
        return;

    var filepath = path.join(js_dir, filename);
    var contents = fs.readFileSync(filepath, 'utf8');
    var messages = [];

    if (!JSLINT(contents, jslint_options)) {
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
