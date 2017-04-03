{Session, Stat} = require './support'
assert = require 'assert'

argv = require('optimist').default({
    time: 60
    users: 5
    'min-wait': 5
    'max-wait': 10
}).argv

class ZulipSession extends Session
    constructor: (id, host, {@username, @password}) ->
        user = @username.split('@')[0]
        super(host, "#{id} #{user}")
        @last_csrf_token = undefined
        @page_params = undefined

    parse_csrf: ->
        match = @last_body.match /name='csrfmiddlewaretoken' value='([a-zA-Z0-9]+)/
        assert match, "Expected CSRF token in form"
        @last_csrf_token = match[1]
        @headers['X-CSRFToken'] = @last_csrf_token

    parse_page_params: ->
        match = @last_body.match /^var page_params = (.*);$/m
        assert match, "Expected page_params"
        @page_params = JSON.parse match[1]
        {@max_message_id, @event_queue_id} = @page_params
        @pointer = @page_params.initial_pointer
        @last_event_id = -1

    login: (cb) ->
        @get '/', =>
            #@get_all(@static)
            @parse_csrf()
            @post '/accounts/login/?next=', {@username, @password}, =>
                @on_app_load(cb)

    on_app_load: (cb) ->
        #@get_all(@app_static)
        @parse_csrf()
        @parse_page_params()

        @update_active_status()
        @get '/json/bots'
        @get '/json/messages', {
            anchor: @pointer
            num_before: 200
            num_after: 200
        }, get_messages_time.cbTimer cb

    reload: (cb) ->
        @get '/', =>
            @on_app_load(cb)

    get_events: ->
        @get '/json/events', {
            @pointer
            last: @max_message_id
            dont_block: false
            queue_id: @event_queue_id
            @last_event_id
        }, (r, body) =>
            response = JSON.parse(body)
            for event in response.events
                @last_event_id = Math.max(@last_event_id, event.id)

                if event.type == 'message'
                    @on_message(event.message)

            @get_events()

    on_message: (message) ->
        if (m = message.content.match /Test message sent at (\d+)/)
            message_latency.update(+new Date() - parseInt(m[1], 10))

    update_active_status: ->
        @post "/json/users/me/presence", {status: "active"}, update_status_time.cbTimer()

    send_stream_message: (stream, subject, content) ->
        @post '/json/messages', {
            client: 'website'
            type: 'stream'
            to: JSON.stringify([stream])
            stream
            subject
            content
        }, message_send_time.cbTimer()

    send_private_message: (recipients, content) ->
        @post '/json/messages', {
            client: 'website'
            type: 'private'
            to: JSON.stringify(recipients)
            reply_to: recipients.join(', ')
            private_message_recipient: recipients.join(', ')
            content
        }, message_send_time.cbTimer()

    random_sends: =>
        s = Math.round(Math.random()*5)
        msg = "Test message sent at #{+new Date()}"

        @send_stream_message("test", "test#{s}", msg)
        setTimeout(@random_sends, @rand_time())

    # TODO: update_message_flags
    # TODO: get_messages

    run_message_test: =>
        @login =>
            @get_events()
            setInterval((=> @update_active_status()), 60*1000)
            @random_sends()

    run_reload_test: =>
        @login @random_reloads

    random_reloads: =>
        @reload total_reload_time.cbTimer =>
            setTimeout(@random_reloads, @rand_time())

    run_test: =>
        opts = argv
        @min_wait = opts['min-wait']
        @max_wait = opts['max-wait']

        switch opts._[0]
            when 'reload' then @run_reload_test()
            when 'message' then @run_message_test()
            else throw new Error("No test selected")

    rand_time: ->
        Math.round(1000 * (@min_wait + Math.random() * (@max_wait - @min_wait)))

host = 'http://localhost:9991'

users = [
    {username: 'iago@zulip.com',     password: 'JhwLkBydEG1tAL5P'}
    {username: 'othello@zulip.com',  password: 'GX5MTQ+qYSzcmDoH'}
    {username: 'cordelia@zulip.com', password: '+1pkoQiP0wEbEvv/'}
    {username: 'hamlet@zulip.com',   password: 'Z/hx5nEcXRQBGzk3'}
    {username: 'prospero@zulip.com', password: 'j+XqHkQ2cycwCQJE'}
]

user_start_step = 1000*1

if argv.users > users.length
    console.log "Only have #{users.length} accounts, so simulating multiple sessions"

for i in [0..argv.users] then do ->
    user = users[i%users.length]
    h = new ZulipSession(i, host, user)
    setTimeout(h.run_test, i*user_start_step)

stats = [
    message_latency = new Stat("Message Latency")
    message_send_time = new Stat("Message Send Time")
    update_status_time = new Stat("/json/update_status_time Time")
    total_reload_time = new Stat("Total reload time")
    get_messages_time = new Stat("/json/get_messages Time")
]

# Reset message latency stat after everyone logs in
# setTimeout(message_latency.reset, (i+1)*user_start_step)

showStats = ->
    for stat in stats when stat.count() > 0
        console.log "#{stat.name}:", stat.stats()
        stat.reset()
    process.exit()

setTimeout(showStats, argv['time']*1000)
