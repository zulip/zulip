var onboarding = (function () {

var exports = {};

// The ordered list of onboarding steps we want new users to complete. If the
// steps are changed here, they must also be changed in create_user.py.
var steps = ["sent_stream_message", "sent_private_message", "made_app_sticky"];
var step_info = {sent_stream_message: {"user_message": "Send a stream message"},
                 sent_private_message: {"user_message": "Send a private message"},
                 made_app_sticky: {"user_message": "Pin this tab"}};

function update_onboarding_steps() {
    var step_statuses = [];
    $.each(steps, function (idx, step) {
        step_statuses.push([step, step_info[step].status]);
    });

    $.ajax({
        type: 'POST',
        url: '/json/update_onboarding_steps',
        dataType: 'json',
        data: {"onboarding_steps": JSON.stringify(step_statuses)}
    });
}

return exports;
}());
