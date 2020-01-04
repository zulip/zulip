const render_pm_list_item = require('../templates/pm_list_item.hbs');

exports.keyed_pm_li = (convo) => {
    const render = () => {
        return render_pm_list_item(convo);
    };

    const eq = (other) => {
        return _.isEqual(convo, other.convo);
    };

    const key = convo.user_ids_string;

    return {
        key: key,
        render: render,
        convo: convo,
        eq: eq,
    };
};

exports.pm_ul = (convos) => {
    const attrs = [
        ['class', 'expanded_private_messages'],
        ['data-name', 'private'],
    ];
    return vdom.ul({
        attrs: attrs,
        keyed_nodes: _.map(convos, exports.keyed_pm_li),
    });
};

window.pm_list_dom = exports;
