request = require 'request'
http = require 'http'
assert = require 'assert'

class @Session
    constructor: (@defaultHost, @name) ->
        @agent = new http.Agent()
        @agent._name = @name
        @jar = request.jar()
        @headers = {'User-agent': "Zulip Load Tester"}
        @last_body = null

    request: (method, url, form, cb) ->
        if url[0] == "/"
            url = "#{@defaultHost}#{url}"

        console.log "#{+new Date() % 1000000} [#{@name}] #{method} #{url}"

        request.get {method, url, form, @agent, @jar, @headers, followAllRedirects:true}, (error, response, body) =>
            if error
                console.error "[#{@name}] Error on #{method} #{url}: #{error}"
            else if response.statusCode != 200
                console.error "[#{@name}] Status #{method} #{response.statusCode} on #{url}"
                console.error body
            else
                @last_body = body
                console.log "#{+new Date() % 1000000} [#{@name} DONE] #{method} #{url}"
                cb(response, body) if cb

    get: (url, cb) ->
        @request "GET", url, undefined, cb

    post: (url, form, cb) ->
        @request "POST", url, form, cb

class @Stat
    constructor: (@name) ->
        @reset()

    reset: =>
        @values = []

    # Start a timer and return a callback that stops the timer and adds
    # the difference to the sample set.
    cbTimer: (cb) ->
        t1 = +new Date()
        return (args...) =>
            @update(+new Date() - t1)
            cb(args...) if cb

    update: (value) ->
        @values.push(value)

    count: -> @values.length

    stats: ->
        @values.sort((a,b) -> a-b)
        {
        count: @values.length
        min: @percentile(0)
        max: @percentile(1)
        median: @percentile(0.50)
        p90:@percentile(0.90)
        }

    percentile: (p) ->
        #Assumes @values has been sorted
        k = (@values.length-1)*p
        f = Math.floor(k)
        c = Math.ceil(k)

        if f == c
            @values[f]
        else
            v0 = @values[f] * (c-k)
            v1 = @values[c] * (k-f)
            v0 + v1
