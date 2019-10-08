var todo_widget = (function () {

var exports = {};

exports.task_data_holder = function () {
    var self = {};

    var all_tasks = [];
    var pending_tasks = [];
    var completed_tasks = [];
    var my_idx = 0;

    self.get_widget_data = function () {

        var widget_data = {
            pending_tasks: pending_tasks,
            completed_tasks: completed_tasks,
        };

        return widget_data;
    };

    self.check_task = {
        task_exists: function (task) {
            var task_exists = _.any(all_tasks, function (item) {
                return item.task === task;
            });
            return task_exists;
        },
    };

    self.handle = {
        new_task: {
            outbound: function (task) {
                var event = {
                    type: 'new_task',
                    key: my_idx,
                    task: task,
                    completed: false,
                };
                my_idx += 1;

                if (!self.check_task.task_exists(task)) {
                    return event;
                }
                return;
            },

            inbound: function (sender_id, data) {
                var idx = data.key;
                var task = data.task;
                var completed = data.completed;

                var task_data = {
                    task: task,
                    user_id: sender_id,
                    key: idx,
                    completed: completed,
                };

                if (!self.check_task.task_exists(task)) {
                    pending_tasks.push(task_data);
                    all_tasks.push(task_data);

                    if (my_idx <= idx) {
                        my_idx = idx + 1;
                    }
                }
            },
        },

        strike: {
            outbound: function (key) {
                var event = {
                    type: 'strike',
                    key: key,
                };

                return event;
            },

            inbound: function (sender_id, data) {
                var key = data.key;
                var task = all_tasks[key];
                var index;

                if (task === undefined) {
                    blueslip.error('unknown key for tasks: ' + key);
                    return;
                }

                all_tasks[key].completed = !all_tasks[key].completed;

                // toggle
                if (task.completed) {
                    index = pending_tasks.indexOf(task);
                    pending_tasks.splice(index, 1);
                    completed_tasks.unshift(task);
                } else {
                    index = completed_tasks.indexOf(task);
                    completed_tasks.splice(index, 1);
                    pending_tasks.push(task);
                }
            },
        },
    };

    self.handle_event = function (sender_id, data) {
        var type = data.type;
        if (self.handle[type]) {
            self.handle[type].inbound(sender_id, data);
        }
    };

    return self;
};

exports.activate = function (opts) {
    var elem = opts.elem;
    var callback = opts.callback;

    var task_data = exports.task_data_holder();

    function render() {
        var html = templates.render('todo-widget');
        elem.html(html);

        elem.find("button.add-task").on('click', function (e) {
            e.stopPropagation();
            elem.find(".widget-error").text('');
            var task = elem.find("input.add-task").val().trim();

            if (task === '') {
                return;
            }

            elem.find(".add-task").val('').focus();

            var task_exists = task_data.check_task.task_exists(task);
            if (task_exists) {
                elem.find(".widget-error").text(i18n.t('Task already exists'));
                return;
            }

            var data = task_data.handle.new_task.outbound(task);
            callback(data);
        });
    }

    function render_results() {
        var widget_data = task_data.get_widget_data();
        var html = templates.render('todo-widget-tasks', widget_data);
        elem.find('ul.todo-widget').html(html);
        elem.find(".widget-error").text('');

        elem.find("button.task").on('click', function (e) {
            e.stopPropagation();
            var key = $(e.target).attr('data-key');

            var data = task_data.handle.strike.outbound(key);
            callback(data);
        });
    }

    elem.handle_events = function (events) {
        _.each(events, function (event) {
            task_data.handle_event(event.sender_id, event.data);
        });
        render_results();
    };

    render();
    render_results();
};

return exports;

}());
if (typeof module !== 'undefined') {
    module.exports = todo_widget;
}

window.todo_widget = todo_widget;
