"use strict";

const people = require("./people");

function person_matcher(query, item) {
    if (people.is_known_user(item)) {
        return composebox_typeahead.query_matches_person(query, item);
    }
    return undefined;
}

function group_matcher(query, item) {
    if (user_groups.is_user_group(item)) {
        return composebox_typeahead.query_matches_name_description(query, item);
    }
    return undefined;
}

exports.set_up = function (input, pills, opts) {
    let source = opts.source;
    if (!opts.source) {
        source = () => user_pill.typeahead_source(pills);
    }
    const include_streams = (query) => opts.stream && query.trim().startsWith("#");
    const include_user_groups = opts.user_group;

    input.typeahead({
        items: 5,
        fixed: true,
        dropup: true,
        source() {
            if (include_streams(this.query)) {
                return stream_pill.typeahead_source(pills);
            }

            if (include_user_groups) {
                return user_group_pill.typeahead_source(pills).concat(source());
            }

            return source();
        },
        highlighter(item) {
            if (include_streams(this.query)) {
                return typeahead_helper.render_stream(item);
            }

            if (include_user_groups) {
                return typeahead_helper.render_person_or_user_group(item);
            }

            return typeahead_helper.render_person(item);
        },
        matcher(item) {
            let query = this.query.toLowerCase();
            query = query.replace(/\u00A0/g, String.fromCharCode(32));

            if (include_streams(query)) {
                query = query.trim().slice(1);
                return item.name.toLowerCase().includes(query);
            }

            if (include_user_groups) {
                return group_matcher(query, item) || person_matcher(query, item);
            }

            return person_matcher(query, item);
        },
        sorter(matches) {
            if (include_streams(this.query)) {
                return typeahead_helper.sort_streams(matches, this.query.trim().slice(1));
            }

            const users = matches.filter(people.is_known_user);
            let groups;
            if (include_user_groups) {
                groups = matches.filter(user_groups.is_user_group);
            }
            return typeahead_helper.sort_recipients(
                users,
                this.query,
                "",
                undefined,
                groups,
                undefined,
            );
        },
        updater(item) {
            if (include_streams(this.query)) {
                stream_pill.append_stream(item, pills);
            } else if (include_user_groups && user_groups.is_user_group(item)) {
                user_group_pill.append_user_group(item, pills);
            } else {
                user_pill.append_user(item, pills);
            }

            input.trigger("focus");
            if (opts.update_func) {
                opts.update_func();
            }
        },
        stopAdvance: true,
    });
};

window.pill_typeahead = exports;
