"use strict";

const settings_data = require("./settings_data");

exports.set_up = function (input, pills, opts) {
    let source = opts.source;
    if (!opts.source) {
        source = () => user_pill.typeahead_source(pills);
    }

    input.typeahead({
        items: 5,
        fixed: true,
        dropup: true,
        source,
        highlighter(item) {
            return typeahead_helper.render_person(item);
        },
        matcher(item) {
            let query = this.query.toLowerCase();
            query = query.replace(/\u00A0/g, String.fromCharCode(32));
            if (!settings_data.show_email()) {
                return item.full_name.toLowerCase().includes(query);
            }
            const email = people.get_visible_email(item);
            return (
                email.toLowerCase().includes(query) || item.full_name.toLowerCase().includes(query)
            );
        },
        sorter(matches) {
            return typeahead_helper.sort_recipientbox_typeahead(this.query, matches, "");
        },
        updater(user) {
            user_pill.append_user(user, pills);
            input.trigger("focus");
            if (opts.update_func) {
                opts.update_func();
            }
        },
        stopAdvance: true,
    });
};

window.pill_typeahead = exports;
