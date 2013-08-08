var onboarding = (function () {

var exports = {};

// The ordered list of onboarding steps we want new users to complete. If the
// steps are changed here, they must also be changed in create_user.py.
var steps = ["sent_stream_message", "sent_private_message", "made_app_sticky"];
// N.B. user_message is **unescaped HTML**, so please use caution
var step_info = {sent_stream_message: {"user_message": "Send a stream message"},
                 sent_private_message: {"user_message": "Send a private message"},
                 made_app_sticky: {"user_message": 'Get our <a id="get-the-app" href="/apps" target="_blank">apps</a>'}};

var onboarding = false;

function update_onboarding_steps() {
    var step_statuses = _.map(steps, function (step) {
        return [step, step_info[step].status];
    });

    $.ajax({
        type: 'POST',
        url: '/json/update_onboarding_steps',
        dataType: 'json',
        data: {"onboarding_steps": JSON.stringify(step_statuses)}
    });
}

function all_steps_completed() {
    return steps.filter(function (step) {
        return step_info[step].status === false;
    }).length === 0;
}


function finish_onboarding() {
    var checklist = $('#onboarding-checklist');
    checklist.empty();
    checklist.html("<i class='icon-vector-check onboarding_success'>Done");
    $('#onboarding').fadeOut(5000, function () {
        $(this).hide();
    });
}

function update_checklist_ui(step) {
    var checklist_item = $($('#onboarding-checklist').find("i")[steps.indexOf(step)]);
    checklist_item.removeClass("icon-vector-check-empty").addClass("icon-vector-check");
    if (all_steps_completed()) {
        finish_onboarding();
    }
}

exports.set_step_info = function (steps) {
    _.each(steps, function (step) {
        var step_name = step[0];
        var status = step[1];
        step_info[step_name].status = status;
        if (status) {
            update_checklist_ui(step_name);
        }
    });
};

exports.mark_checklist_step = function (step) {
    if (!onboarding || step_info[step].status) {
        return;
    }

    step_info[step].status = true;
    update_checklist_ui(step);
    update_onboarding_steps();
};

function set_up_checklist() {
    var onboarding_checklist = $('#onboarding-checklist').empty();
    if (all_steps_completed()) {
        return;
    }

    _.each(steps, function (step) {
        var entry = $('<div>');
        if (step_info[step].status) {
            entry.append($("<i class='icon-vector-check'>"));
        } else {
            entry.append($("<i class='icon-vector-check-empty'>"));
        }
        entry.append($('<span>').html(step_info[step].user_message)).attr("id", step);
        onboarding_checklist.append(entry);

        var register_action = step_info[step].register;
        if (register_action !== undefined) {
            register_action(step_info[step].status);
        }

        $(document.body).one('click', "#get-the-app", function (e) {
            exports.mark_checklist_step("made_app_sticky");
        });

        $("#onboarding").show();
    });
}

exports.initialize = function () {
    onboarding = true;
    exports.set_step_info(page_params.onboarding_steps);
    set_up_checklist();
};

return exports;
}());
