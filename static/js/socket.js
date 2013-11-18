function Socket(url) {
    this.url = url;
    this._is_open = false;
    this._is_authenticated = false;
    this._is_reconnecting = false;
    this._reconnect_initiation_time = null;
    this._send_queue = [];
    this._next_req_id = 0;
    this._requests = {};
    this._connection_failures = 0;
    this._reconnect_timeout_id = null;
    this._heartbeat_timeout_id = null;

    this._is_unloading = false;
    $(window).on("unload", function () {
        this._is_unloading = true;
    });

    $(document).on("unsuspend", function () {
        this._try_to_reconnect();
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
            this._try_to_reconnect();
            return;
        }

        this._do_send('request', msg, success, error);
    },

    _do_send: function Socket__do_send(type, msg, success, error) {
        var req_id = this._next_req_id;
        var that = this;
        this._next_req_id++;
        this._requests[req_id] = {type: type, request: msg, success: success,
                                  error: error};
        this._requests[req_id].ack_timeout_id = setTimeout(function () {
            blueslip.info("Timeout on ACK for request " + req_id);
            that._try_to_reconnect();
        }, 2000);

        // TODO: I think we might need to catch exceptions here for certain transports
        this._sockjs.send(JSON.stringify({req_id: req_id,
                                          type: type, request: msg}));
    },

    _can_send: function Socket__can_send() {
        return this._is_open && this._is_authenticated;
    },

    _resend: function Socket__resend(req_id) {
        var req_info = this._requests[req_id];
        if (req_info.ack_timeout_id !== null) {
            clearTimeout(req_info.ack_timeout_id);
            req_info.ack_timeout_id = null;
        }
        delete this._requests[req_id];

        if (req_info.type !== 'request') {
            blueslip.error("Cannot resend message of type: " + req_info.type);
            return;
        }

        this.send(req_info.request, req_info.success, req_info.error);
    },

    _drain_queue: function Socket__drain_queue() {
        var that = this;
        var queue = this._send_queue;
        this._send_queue = [];
        _.each(queue, function (elem) {
            that.send(elem.msg, elem.success, elem.error);
        });
    },

    _process_response: function Socket__process_response(req_id, response) {
        var req_info = this._requests[req_id];
        if (req_info === undefined) {
            if (req_id >= this._next_req_id) {
                blueslip.error("Got a response for an unknown request",
                               {request_id: req_id, next_id: this._next_req_id,
                                outstanding_ids: _.keys(this._requests)});
            }
            // There is a small race where we might start reauthenticating
            // before one of our requests has finished but then have the request
            // finish and thus receive the finish notification both from the
            // status inquiry and from the normal response.  Therefore, we might
            // be processing the response for a request where we already got the
            // response from a status inquiry.  In that case, don't process the
            // response twice.
            return;
        }

        if (response.result === 'success') {
            req_info.success(response);
        } else {
            req_info.error('response', response);
        }
        delete this._requests[req_id];
    },

    _process_ack: function Socket__process_ack(req_id) {
        var req_info = this._requests[req_id];
        if (req_info === undefined) {
            blueslip.error("Got an ACK for an unknown request",
                           {request_id: req_id, next_id: this._next_req_id,
                            outstanding_ids: _.keys(this._requests)});
            return;
        }

        if (req_info.ack_timeout_id !== null) {
            clearTimeout(req_info.ack_timeout_id);
            req_info.ack_timeout_id = null;
        }
    },

    _setup_sockjs_callbacks: function Socket__setup_sockjs_callbacks(sockjs) {
        var that = this;
        sockjs.onopen = function Socket__sockjs_onopen() {
            blueslip.info("Socket connected.");
            that._is_open = true;

            // We can only authenticate after the DOM has loaded because we need
            // the CSRF token
            $(function () {
                that._do_send('auth', {csrf_token: csrf_token,
                                       queue_id: page_params.event_queue_id,
                                       status_inquiries: _.keys(that._requests)},
                              function (resp) {
                                  that._is_authenticated = true;
                                  that._is_reconnecting = false;
                                  that._reconnect_initiation_time = null;
                                  that._connection_failures = 0;
                                  _.each(resp.status_inquiries, function (status, id) {
                                      if (status.status === 'complete') {
                                          that._process_response(id, status.response);
                                      }
                                      if (status.status === 'not_received') {
                                          that._resend(id);
                                      }
                                  });
                                  that._drain_queue();
                              },
                              function (type, resp) {
                                  blueslip.info("Could not authenticate with server: " + resp.msg);
                                  that._connection_failures++;
                                  that._try_to_reconnect(that._reconnect_wait_time());
                              });
            });
        };

        sockjs.onmessage = function Socket__sockjs_onmessage(event) {
            if (event.data.type === 'ack') {
                that._process_ack(event.data.req_id);
            } else {
                that._process_response(event.data.req_id, event.data.response);
            }
        };

        sockjs.onheartbeat = function Socket__socjks_onheartbeat() {
            if (that._heartbeat_timeout_id !== null) {
                clearTimeout(that._heartbeat_timeout_id);
                that._heartbeat_timeout_id = null;
            }
            that._heartbeat_timeout_id = setTimeout(function () {
                that._heartbeat_timeout_id = null;
                blueslip.info("Missed too many hearbeats");
                that._try_to_reconnect();
            }, 60000);
        };

        sockjs.onclose = function Socket__sockjs_onclose() {
            if (that._is_unloading) {
                return;
            }
            blueslip.info("SockJS connection lost.  Attempting to reconnect soon.");
            that._connection_failures++;
            that._is_reconnecting = false;
            that._try_to_reconnect(that._reconnect_wait_time());
        };
    },

    _reconnect_wait_time: function Socket__reconnect_wait_time() {
        if (this._connection_failures === 1) {
            // We specify a non-zero timeout here so that we don't try to
            // immediately reconnect when the page is refreshing
            return 30;
        } else {
            return Math.min(90, Math.exp(this._connection_failures/2)) * 1000;
        }
    },

    _try_to_reconnect: function Socket__try_to_reconnect(wait_time) {
        if (wait_time === undefined) {
            wait_time = 0;
        }
        var that = this;

        var now = (new Date()).getTime();
        if (this._is_reconnecting && now - this._reconnect_initiation_time < 1000) {
            // Only try to reconnect once a second
            return;
        }

        if (this._reconnect_timeout_id !== null) {
            clearTimeout(this._reconnect_timeout_id);
            this._reconnect_timeout_id = null;
        }

        if (this._heartbeat_timeout_id !== null) {
            clearTimeout(that._heartbeat_timeout_id);
            this._heartbeat_timeout_id = null;
        }

        this._is_open = false;
        this._is_authenticated = false;
        this._is_reconnecting = true;
        this._reconnect_initiation_time = now;

        this._reconnect_timeout_id = setTimeout(function () {
            that._reconnect_timeout_id = null;
            blueslip.info("Attempting socket reconnect.");
            that._sockjs = new SockJS(that.url, null, {protocols_whitelist: that._supported_protocols});
            that._setup_sockjs_callbacks(that._sockjs);
        }, wait_time);
    }
};
