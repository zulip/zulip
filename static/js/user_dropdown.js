/*
    This module lets you create a dropdown list of all
    active humans.

    Right now the only use case is to select the owner
    of a bot, but we can generalize this code going forward
    for other use cases.  Right now it should be quick to
    audit the code to find places where we specifically
    hard-code stuff for the bot owner case.  See
    'bot_owner_select' as an example.
*/

const render_user_dropdown = require("../templates/user_dropdown.hbs");

exports.create = (current_user_id) => {
    const users = people.get_active_humans();
    const info = {
        users: users,
        name: 'bot_owner_select', // used for label
    };

    const html = render_user_dropdown(info);
    const elem = $(html);

    if (current_user_id) {
        elem.val(current_user_id);
    }

    return {
        elem: elem,
        get_user_id: () => elem.val(),
    };
};
