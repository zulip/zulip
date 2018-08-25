var invite_stream_pill = (function () {

var exports = {};

exports.create_item_from_stream_name = function (stream_name, current_items) {
    var find_in_existing_pills = _.find(current_items, function (item) {
        return item.display_value === stream_name;
    });
    if (find_in_existing_pills) {
        return;
    }

    var find_in_invite_streams = _.find(invite.get_invite_streams(), function (stream) {
        return stream.name === stream_name;
    });
    if (find_in_invite_streams === undefined) {
        return;
    }

    return {
        display_value: stream_data.get_name(stream_name),
    };
};

exports.get_stream_name_from_item = function (item) {
    return item.display_value;
};

exports.initialize_pill = function (pill_container) {
    var pills = input_pill.create({
        container: pill_container,
        create_item_from_text: exports.create_item_from_stream_name,
        get_text_from_item: exports.get_stream_name_from_item,
    });

    var input = pill_container.children('.input');
    exports.set_up_typeahead_on_pills(input, pills);

    _.each(stream_data.get_default_stream_names(), function (name) {
        pills.appendValue(name, pills);
    });

    pills.onPillCreate(function () {
        pills.clear_text();
    });

    return pills;
};

exports.typeahead_source = function (pills) {
    var taken_streams = _.pluck(pills.items(), 'display_value');
    var items = _.filter(invite.get_invite_streams() , function (item) {
        return taken_streams.indexOf(item.name) === -1;
    });
    return items;
};

exports.set_up_typeahead_on_pills = function (input, pills) {
    input.typeahead({
        items: 100,
        fixed: true,
        dropup: true,
        source: function () {
            return exports.typeahead_source(pills);
        },
        highlighter: function (item) {
            return item.name;
        },
        matcher: function (item) {
            var query = this.query.toLowerCase();
            return item.name.toLowerCase().indexOf(query) !== -1;
        },
        sorter: function (matches) {
            matches.sort(function (a, b) {
                return a.name.toLowerCase() > b.name.toLowerCase();
            });
            return matches;
        },
        updater: function (item) {
            pills.appendValue(item.name, pills);
            input.focus();
        },
        stopAdvance: true,
    });
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = invite_stream_pill;
}

window.invite_stream_pill = invite_stream_pill;
