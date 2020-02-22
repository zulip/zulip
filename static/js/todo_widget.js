const render_widgets_todo_widget = require('../templates/widgets/todo_widget.hbs');
const render_widgets_todo_widget_tasks = require('../templates/widgets/todo_widget_tasks.hbs');

exports.task_data_holder = function () {
    const self = {};

    const all_tasks = [];
    const pending_tasks = [];
    const completed_tasks = [];
    let my_idx = 0;

    self.get_widget_data = function () {

        const widget_data = {
            pending_tasks: pending_tasks,
            completed_tasks: completed_tasks,
        };

        return widget_data;
    };

    self.check_task = {
        task_exists: function (task) {
            const task_exists = all_tasks.some(item => item.task === task);
            return task_exists;
        },
    };

    self.handle = {
        new_task: {
            outbound: function (task, desc) {
                const event = {
                    type: 'new_task',
                    key: my_idx,
                    task: task,
                    desc: desc,
                    completed: false,
                };
                my_idx += 1;

                if (!self.check_task.task_exists(task)) {
                    return event;
                }
                return;
            },

            inbound: function (sender_id, data) {
                const idx = data.key;
                const task = data.task;
                const desc = data.desc;
                const completed = data.completed;

                const task_data = {
                    task: task,
                    desc: desc,
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
                const event = {
                    type: 'strike',
                    key: key,
                };

                return event;
            },

            inbound: function (sender_id, data) {
                const key = data.key;
                const task = all_tasks[key];
                let index;

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
        const type = data.type;
        if (self.handle[type]) {
            self.handle[type].inbound(sender_id, data);
        }
    };

    return self;
};

exports.activate = function (opts) {
    const elem = opts.elem;
    const callback = opts.callback;

    const task_data = exports.task_data_holder();

    function render() {
        const html = render_widgets_todo_widget();
        elem.html(html);

        elem.find("button.add-task").on('click', function (e) {
            e.stopPropagation();
            elem.find(".widget-error").text('');
            const task = elem.find("input.add-task").val().trim();
            const desc = elem.find("input.add-desc").val().trim();

            if (task === '') {
                return;
            }

            elem.find(".add-task").val('').focus();
            elem.find(".add-desc").val('').focus();

            const task_exists = task_data.check_task.task_exists(task);
            if (task_exists) {
                elem.find(".widget-error").text(i18n.t('Task already exists'));
                return;
            }

            const data = task_data.handle.new_task.outbound(task, desc);
            callback(data);
        });
    }

    function render_results() {
        const widget_data = task_data.get_widget_data();
        const html = render_widgets_todo_widget_tasks(widget_data);
        elem.find('ul.todo-widget').html(html);
        elem.find(".widget-error").text('');

        elem.find("button.task").on('click', function (e) {
            e.stopPropagation();
            const key = $(e.target).attr('data-key');

            const data = task_data.handle.strike.outbound(key);
            callback(data);
        });
    }

    elem.handle_events = function (events) {
        for (const event of events) {
            task_data.handle_event(event.sender_id, event.data);
        }

        render_results();
    };

    render();
    render_results();
};

window.todo_widget = exports;
