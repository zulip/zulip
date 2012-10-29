"use strict";

// Global variables, categorized by place of definition.
var globals =
    // Third-party libraries
      ' $ jQuery Spinner Handlebars XDate'

    // index.html
    + ' initial_pointer email stream_list people_list have_initial_messages'

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

    // search.js
    + ' search_button_handler something_is_highlighted update_highlight_on_narrow'

    // setup.js
    + ' loading_spinner templates'

    // subs.js
    + ' subs'

    // ui.js
    + ' register_onclick hide_email show_email'
    + ' report_error report_success report_message clicking mouse_moved'
    + ' update_autocomplete autocomplete_needs_update'

    // zephyr.js
    + ' message_array message_dict get_updates_params'
    + ' clear_table add_to_table subject_dict'
    + ' keep_pointer_in_view move_pointer_at_page_top_and_bottom'
    + ' respond_to_message'
    + ' select_message select_message_by_id'
    + ' scroll_to_selected'
    + ' selected_message selected_message_id'
    + ' start_reload_app reloading_app do_reload_app_preserving_compose'
    + ' at_top_of_viewport at_bottom_of_viewport'
    + ' viewport'
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
