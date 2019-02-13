var user_search = function (opts) {
    // This is mostly view code to manage the user search widget
    // above the buddy list.  We rely on other code to manage the
    // details of populating the list when we change.

    var self = {};

    var $widget = $('#user_search_section').expectOne();
    var $input = $('.user-list-filter').expectOne();

    self.input_field = function () {
        return $input;
    };

    self.text = function () {
        return $input.val().trim();
    };

    self.searching = function () {
        return $input.is(':focus');
    };

    self.empty = function () {
        return self.text() === '';
    };

    self.clear_search = function () {
        if (self.empty()) {
            self.close_widget();
            return;
        }

        $input.val('');
        $input.blur();
        opts.reset_items();
    };

    self.escape_search = function () {
        if (self.empty()) {
            self.close_widget();
            return;
        }

        $input.val('');
        opts.update_list();
    };

    self.hide_widget = function () {
        $widget.addClass('notdisplayed');
    };

    self.show_widget = function () {
        // Hide all the popovers but not userlist sidebar
        // when the user wants to search.
        popovers.hide_all_except_userlist_sidebar();
        $widget.removeClass('notdisplayed');
    };

    self.widget_shown = function () {
        return $widget.hasClass('notdisplayed');
    };

    self.clear_and_hide_search = function () {
        if (!self.empty()) {
            $input.val('');
            opts.update_list();
        }
        self.close_widget();
    };

    self.close_widget = function () {
        $input.blur();
        self.hide_widget();
        opts.reset_items();
    };

    self.expand_column = function () {
        var column = $input.closest(".app-main [class^='column-']");
        if (!column.hasClass("expanded")) {
            popovers.hide_all();
            if (column.hasClass('column-left')) {
                stream_popover.show_streamlist_sidebar();
            } else if (column.hasClass('column-right')) {
                popovers.show_userlist_sidebar();
            }
        }
    };

    self.initiate_search = function () {
        self.expand_column();
        self.show_widget();
        $input.focus();
    };

    self.toggle_filter_displayed = function () {
        if (self.widget_shown()) {
            self.initiate_search();
        } else {
            self.clear_and_hide_search();
        }
    };

    function on_focus(e) {
        opts.on_focus();
        e.stopPropagation();
    }

    $('#clear_search_people_button').on('click', self.clear_search);
    $('#userlist-header').on('click', self.toggle_filter_displayed);

    $input.on('input', opts.update_list);
    $input.on('focus', on_focus);

    return self;
};

if (typeof module !== 'undefined') {
    module.exports = user_search;
}
window.user_search = user_search;
