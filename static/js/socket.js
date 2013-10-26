function Socket(url) {
    this.url = url;
    this._is_open = false;
    this._is_authenticated = false;
    this._send_queue = [];
    this._next_req_id = 0;
    this._requests = {};
    this._connection_failures = 0;

    this._is_unloading = false;
    $(window).on("unload", function () {
        this._is_unloading = true;
    });

    this._supported_protocols = ['websocket', 'xdr-streaming', 'xhr-streaming',
                                 'xdr-polling', 'xhr-polling', 'jsonp-polling'];
    if (page_params.test_suite) {
        this._supported_protocols = _.reject(this._supported_protocols,
                                             function (x) { return x === 'xhr-streaming'; });
    }

    this._sockjs = new SockJS(url, null, {protocols_whitelist: this._supported_protocols});
    this._setup_sockjs_callbacks(this._sockjs);
}

Socket.prototype = {
    send: function Socket_send(msg, success, error) {
        if (! this._can_send()) {
            this._send_queue.push({msg: msg, success: success, error: error});
            return;
        }

        this._do_send('request', msg, success, error);
    },

    _do_send: function Socket__do_send(type, msg, success, error) {
        var req_id = this._next_req_id;
        this._next_req_id++;
        this._requests[req_id] = {success: success, error: error};
        // TODO: I think we might need to catch exceptions here for certain transports
        this._sockjs.send(JSON.stringify({client_meta: {req_id: req_id},
                                          type: type, request: msg}));
    },

    _can_send: function Socket__can_send() {
        return this._is_open && this._is_authenticated;
    },

    _drain_queue_send: function Socket__drain_queue_send() {
        var that = this;
        var queue = this._send_queue;
        this._send_queue = [];
        _.each(queue, function (elem) {
            that.send(elem.msg, elem.success, elem.error);
        });
    },

    _drain_queue_error: function Socket__drain_queue_error() {
        var that = this;
        var queue = this._send_queue;
        this._send_queue = [];
        _.each(queue, function (elem) {
            elem.error('connection');
        });
    },

    _setup_sockjs_callbacks: function Socket__setup_sockjs_callbacks(sockjs) {
        var that = this;
        sockjs.onopen = function Socket__sockjs_onopen() {
            blueslip.info("Socket connected.");
            that._is_open = true;

            // We can only authenticate after the DOM has loaded because we need
            // the CSRF token
            $(function () {
                that._do_send('auth', {csrf_token: csrf_token},
                              function () {
                                  that._is_authenticated = true;
                                  that._connection_failures = 0;
                                  that._drain_queue_send();
                              },
                              function (type, resp) {
                                  blueslip.info("Could not authenticate with server: " + resp.msg);
                                  that._try_to_reconnect();
                              });
            });
        };

        sockjs.onmessage = function Socket__sockjs_onmessage(event) {
            var req_id = event.data.client_meta.req_id;
            var req_info = that._requests[req_id];
            if (req_info === undefined) {
                blueslip.error("Got a response for an unknown request");
                return;
            }

            if (event.data.response.result === 'success') {
                req_info.success(event.data.response);
            } else {
                req_info.error('response', event.data.response);
            }
            delete that._requests[req_id];
        };

        sockjs.onclose = function Socket__sockjs_onclose() {
            if (that._is_unloading) {
                return;
            }
            blueslip.info("SockJS connection lost.  Attempting to reconnect soon.");
            that._try_to_reconnect();
        };
    },

    _try_to_reconnect: function Socket__try_to_reconnect() {
        var that = this;
        this._is_open = false;
        this._is_authenticated = false;
        this._connection_failures++;
        this._drain_queue_error();

        var wait_time;
        if (this._connection_failures === 1) {
            // We specify a non-zero timeout here so that we don't try to
            // immediately reconnect when the page is refreshing
            wait_time = 30;
        } else {
            wait_time = Math.min(90, Math.exp(this._connection_failures/2)) * 1000;
        }

        setTimeout(function () {
            blueslip.info("Attempting socket reconnect.");
            that._sockjs = new SockJS(that.url, null, {protocols_whitelist: that._supported_protocols});
            that._setup_sockjs_callbacks(that._sockjs);
        }, wait_time);
    }
};
