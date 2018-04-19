var buddy_list = (function () {
    var self = {};

    self.populate = function (opts) {
        var user_info = opts.items;

        var html = templates.render('user_presence_rows', {users: user_info});
        $('#user_presences').html(html);
    };

    self.find_li = function (opts) {
        var user_id = opts.key;
        return $("li.user_sidebar_entry[data-user-id='" + user_id + "']");
    };

    self.insert_or_move = function (opts) {
        var user_id = opts.key;
        var info = opts.item;
        var compare_function = opts.compare_function;

        $('#user_presences').find('[data-user-id="' + user_id + '"]').remove();
        var html = templates.render('user_presence_row', info);

        var items = $('#user_presences li').toArray();

        function insert() {
            var i = 0;

            for (i = 0; i < items.length; i += 1) {
                var li = $(items[i]);
                var list_user_id = li.attr('data-user-id');
                if (compare_function(user_id, list_user_id) < 0) {
                    li.before(html);
                    return;
                }
            }

            $('#user_presences').append(html);
        }

        insert();
    };

    return self;
}());

if (typeof module !== 'undefined') {
    module.exports = buddy_list;
}

