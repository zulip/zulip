const render_widgets_todo_widget = require('../templates/widgets/todo_widget.hbs');
const render_widgets_todo_widget_tasks = require('../templates/widgets/todo_widget_tasks.hbs');

exports.task_data_holder = function () {
    const self = {};

    const all_tasks = [];
    let my_idx = 1;

    self.get_widget_data = function () {
        all_tasks.sort((a, b) => a.task.localeCompare(b.task));

        const pending_tasks = [];
        const completed_tasks = [];

        for (const item of all_tasks) {
            if (item.completed) {
                completed_tasks.push(item);
            } else {
                pending_tasks.push(item);
            }
        }

        const widget_data = {
            pending_tasks: pending_tasks,
            completed_tasks: completed_tasks,
        };

        return widget_data;
    };

    self.name_in_use = function (name) {
        const task_exists = all_tasks.some(item => item.task === name);
        return task_exists;
    };


    self.check_task = {
        get_task_index: function (list, val) {
            return Object.keys(list).find(index => list[index].key === val);
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

                if (!self.name_in_use(task)) {
                    return event;
                }
                return;
            },

            inbound: function (sender_id, data) {
                const idx = data.key;
                const key = idx + "," + sender_id;
                const task = data.task;
                const desc = data.desc;
                const completed = data.completed;

                const task_data = {
                    task: task,
                    desc: desc,
                    user_id: sender_id,
                    key: key,
                    completed: completed,
                };

                if (!self.name_in_use(task)) {
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
                const task_index = self.check_task.get_task_index(all_tasks, key);
                const task = all_tasks[task_index];
                let index;

                if (task === undefined) {
                    blueslip.error('unknown key for tasks: ' + key);
                    return;
                }

                all_tasks[task_index].completed = !all_tasks[task_index].completed;
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

            const task_exists = task_data.name_in_use(task);
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
