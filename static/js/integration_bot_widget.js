// This function subscribes the newly created bot to the stream specified by the user.
function subscribe_to_stream(bot_email, stream_name) {
    const bot_user_id = people.get_user_id(bot_email);
    stream_data.add_subscriber(stream_name, bot_user_id);
}

// This function puts together the main string for url that will be copied by the user
// to use for incoming webhook services.
function put_key_values_in_url(api_url, integration_url,
                               bot_api_key, stream_name) {
    const integration_bot_url = api_url + integration_url +
                              "?api_key=" + bot_api_key +
                              "&stream=" + stream_name;
    return integration_bot_url;
}

// This function returns the div/span where the integration bot url string will be
// set for the user.
function get_url_span() {
    // This div or span value can be updated along with building the UI using this widget.
    return $("#integration_bot_url");
}

function update_integration_bot_url(integration_bot_url) {
    const url_span = get_url_span();
    url_span.text(integration_bot_url);
}

// This is the function that runs after the bot is created successfully.
function on_create_bot_success(result, stream_name, api_url, integration_url) {
    const bot_api_key = result.api_key;
    const bot_email = result.email;

    subscribe_to_stream(bot_email, stream_name);
    const integration_bot_url = put_key_values_in_url(api_url, integration_url,
                                                      bot_api_key, stream_name);
    update_integration_bot_url(integration_bot_url);
}

function create_bot(full_name, short_name, bot_avatar_file, stream_name,
                    api_url, integration_url, on_success) {
    const formData = new FormData();
    formData.append('csrfmiddlewaretoken', csrf_token);
    formData.append('full_name', full_name);
    formData.append('short_name', short_name);
    formData.append('file-' + 0, bot_avatar_file);
    channel.post({
        url: '/json/bots',
        data: formData,
        cache: false,
        processData: false,
        contentType: false,
        success: function (resp, statusText, xhr) {
            const result = JSON.parse(xhr.responseText);
            on_success(result, stream_name, api_url, integration_url);
        },
        error: function (xhr) {
            // UI yet to be created with this div id
            $('#bot_widget_error').text(JSON.parse(xhr.responseText).msg).show();
        },
    });
}

// This is the main function to be called to set the integration bot url.
exports.set_integration_bot_url = function (
    api_url, integration_url, bot_full_name,
    bot_short_name, bot_avatar_file, bot_owner, stream_name
) {
    create_bot(bot_full_name, bot_short_name, bot_avatar_file,
               stream_name, api_url, integration_url, on_create_bot_success);
};

window.integration_bot_widget = exports;
