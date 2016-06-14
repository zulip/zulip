set_global('$', function () {});
global.$ = require('jQuery');
$.fn.autosize = function () {
    return;
};

var doc = {
    location: {
        protocol: "",
        hos: ""
    }
}
set_global('document', doc);

var flags = {
    use_socket: ""
}
set_global('feature_flags', flags);

var window = {
    XMLHttpRequest: ""
}
set_global('window', window);

set_global('channel', {});
var data = {events: [{type: 'stream', op: 'update', id: 1, other: 'thing'}]};
global.channel.post = function (options) {
    options.success(data);
};

add_dependencies({
    Handlebars: 'handlebars',
    people: 'js/people.js',
    compose: 'js/compose.js',
    stream_data: 'js/stream_data.js',
    util: 'js/util.js'

});

set_global('page_params', {
    people_list: [],
    email: 'hamlet@example.com'
});


set_global('blueslip', {
    error: function() {
        return;
    }
});

status_classes = "";

(function test_users_in_realm() {
    $.trim = function () {return;};
    compose.recipient = function() {
        return "alice1@example.com";
    }

    
    var alice1 = {
        email: 'alice1@example.com',
        full_name: 'Alice'
    };
    people.add(alice1);

    var alice2 = {
        email: 'alice2@example.com',
        full_name: 'Alice'
    };
    people.add(alice2);
    
   console.log(compose.validate());
}());