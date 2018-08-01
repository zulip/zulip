var stream_settings_list = (function () {

var exports = {};

function create_list() {
    self.container_sel = '#subscriptions_table .streams-list';

    self.items_to_html = function (opts) {
        var template_data = {
            subscriptions: opts.items,
        };
        var html = templates.render('subscriptions', template_data);
        return html;
    };

    self.get_data_from_keys = function (opts) {
        var stream_ids = opts.keys;

        var sub_rows = _.map(stream_ids, function (stream_id) {
            return stream_data.get_sub_by_id(stream_id);
        });

        return sub_rows;
    };

    // generic code below

    self.populate = function (opts) {
        var items = self.get_data_from_keys({
            keys: opts.keys,
        });

        var html = self.items_to_html({
            items: items,
        });

        $(self.container_sel).html(html);
    };

    return self;
}

function triage_stream(query, sub) {
    if (query.subscribed_only) {
        // reject non-subscribed streams
        if (!sub.subscribed) {
            return 'rejected';
        }
    }

    var search_terms = search_util.get_search_terms(query.input);

    function match(attr) {
        var val = sub[attr];

        return search_util.vanilla_match({
            val: val,
            search_terms: search_terms,
        });
    }

    if (match('name')) {
        return 'name_match';
    }

    if (match('description')) {
        return 'desc_match';
    }

    return 'rejected';
}

function get_stream_id_buckets(stream_ids, query) {
    var buckets = {
        name: [],
        desc: [],
    };

    _.each(stream_ids, function (stream_id) {
        var sub = stream_data.get_sub_by_id(stream_id);
        var match_status = triage_stream(query, sub);

        if (match_status === 'name_match') {
            buckets.name.push(stream_id);
        } else if (match_status === 'desc_match') {
            buckets.desc.push(stream_id);
        }
    });

    stream_data.sort_for_stream_settings(buckets.name);
    stream_data.sort_for_stream_settings(buckets.desc);

    return buckets;
}

function get_stream_ids(query) {
    var sub_rows = stream_data.get_updated_unsorted_subs();

    var stream_ids = _.map(sub_rows, function (sub) {
        return sub.stream_id;
    });

    var buckets = get_stream_id_buckets(stream_ids, query);
    var ids_to_show = [].concat(
        buckets.name,
        buckets.desc
    );

    return ids_to_show;
}

exports.list = create_list();

exports.repopulate = function (query) {
    var keys = get_stream_ids(query);

    exports.list.populate({
        keys: keys,
    });
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = stream_settings_list;
}
window.stream_settings_list = stream_settings_list;
