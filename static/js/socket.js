var Socket = (function () {

var CLOSE_REASONS = {
    none_given:   {code: 4000, msg: "No reason provided"},
    no_heartbeat: {code: 4001, msg: "Missed too many heartbeats"},
    auth_fail:    {code: 4002, msg: "Authentication failed"},
    ack_timeout:  {code: 4003, msg: "ACK timeout"},
    cant_send:    {code: 4004, msg: "User attempted to send while Socket was not ready"},
    unsuspend:    {code: 4005, msg: "Got unsuspend event"},
};

function Socket(url) {
    this.url = url;
    this._is_open = false;
    this._is_authenticated = false;
    this._is_reconnecting = false;
    this._reconnect_initiation_time = null;
    this._next_req_id_counter = 0;
    this._connection_failures = 0;
    this._reconnect_timeout_id = null;
    this._heartbeat_timeout_id = null;
    this._localstorage_requests_key = 'zulip_socket_requests';
    this._requests = this._localstorage_requests();

    var that = this;
    this._is_unloading = false;
    $(window).on("unload", function () {
        that._is_unloading = true;
    });

    $(document).on("unsuspend", function () {
        that._try_to_reconnect({reason: 'unsuspend'});
    });

    this._supported_protocols = ['websocket', 'xdr-streaming', 'xhr-streaming',
                                 'xdr-polling', 'xhr-polling', 'jsonp-polling'];
    if (page_params.test_suite) {
        this._supported_protocols = _.reject(this._supported_protocols,
                                             function (x) { return x === 'xhr-streaming'; });
        // Don't create the SockJS on startup when running under the test suite.
        // The first XHR request gets considered part of the page load and
        // therefore the PhantomJS onLoadFinished handler doesn't get called
        // until the SockJS XHR finishes, which happens at the heartbeat, 25
        // seconds later.  The SockJS objects will be created on demand anyway.
    } else {
        this._create_sockjs_object();
    }
}

Socket.prototype = {
    _create_sockjs_object: function Socket__create_sockjs_object() {
        this._sockjs = new SockJS(this.url, null, {protocols_whitelist: this._supported_protocols});
        this._setup_sockjs_callbacks(this._sockjs);
    },

    _make_request: function Socket__make_request(type) {
        return {req_id: this._get_next_req_id(),
                type: type,
                state: 'pending'};
    },

    // Note that by default messages are queued and retried across
    // browser restarts if a restart takes place before a message
    // is successfully transmitted.
    // If that is the case, the success/error callbacks will not
    // be automatically called.
    send: function Socket__send(msg, success, error) {
        var request = this._make_request('request');
        request.msg = msg;
        request.success = success;
        request.error = error;
        this._save_request(request);

        if (! this._can_send()) {
            this._try_to_reconnect({reason: 'cant_send'});
            return;
        }

        this._do_send(request);
    },

    _get_next_req_id: function Socket__get_next_req_id() {
        var req_id = page_params.queue_id + ':' + this._next_req_id_counter;
        this._next_req_id_counter += 1;
        return req_id;
    },

    _req_id_too_new: function Socket__req_id_too_new(req_id) {
        var counter = req_id.split(':')[2];

        return parseInt(counter, 10) >= this._next_req_id_counter;
    },

    _req_id_sorter: function Socket__req_id_sorter(req_id_a, req_id_b) {
        // Sort in ascending order
        var a_count = parseInt(req_id_a.split(':')[2], 10);
        var b_count = parseInt(req_id_b.split(':')[2], 10);

        return a_count - b_count;
    },

    _do_send: function Socket__do_send(request) {
        var that = this;
        this._requests[request.req_id].ack_timeout_id = setTimeout(function () {
            blueslip.info("Timeout on ACK for request " + request.req_id);
            that._try_to_reconnect({reason: 'ack_timeout'});
        }, 2000);

        try {
            this._update_request_state(request.req_id, 'sent');
            this._sockjs.send(JSON.stringify({req_id: request.req_id,
                                              type: request.type, request: request.msg}));
        } catch (e) {
            this._update_request_state(request.req_id, 'pending');
            if (e instanceof Error && e.message === 'INVALID_STATE_ERR') {
                // The connection was somehow closed.  Our on-close handler will
                // be called imminently and we'll retry this request upon reconnect.
                return;
            } else if (e instanceof Error && e.message.indexOf("NS_ERROR_NOT_CONNECTED") !== -1) {
                // This is a rarely-occurring Firefox error.  I'm not sure
                // whether our on-close handler will be called, so let's just
                // call close() explicitly.
                this._sockjs.close();
                return;
            }
            throw e;
        }
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

        if (req_info.type !== 'request') {
            return;
        }

        this._do_send(req_info);
    },

    _process_response: function Socket__process_response(req_id, response) {
        var req_info = this._requests[req_id];
        if (req_info === undefined) {
            if (this._req_id_too_new(req_id)) {
                blueslip.error("Got a response for an unknown request",
                               {request_id: req_id, next_id: this._next_req_id_counter,
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

        if (response.result === 'success' && req_info.success !== undefined) {
            req_info.success(response);
        } else if (req_info.error !== undefined) {
            req_info.error('response', response);
        }
        this._remove_request(req_id);
    },

    _process_ack: function Socket__process_ack(req_id) {
        var req_info = this._requests[req_id];
        if (req_info === undefined) {
            blueslip.error("Got an ACK for an unknown request",
                           {request_id: req_id, next_id: this._next_req_id_counter,
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
            blueslip.info("Socket connected [transport=" + sockjs.protocol + "]");
            if (that._reconnect_initiation_time !== null) {
                // If this is a reconnect, network was probably
                // recently interrupted, so we optimistically restart
                // get_events
                server_events.restart_get_events();
            }
            that._is_open = true;

            // Notify listeners that we've finished the websocket handshake
            $(document).trigger($.Event('websocket_postopen.zulip', {}));

            // We can only authenticate after the DOM has loaded because we need
            // the CSRF token
            $(function () {
                var request = that._make_request('auth');
                request.msg = {csrf_token: csrf_token,
                               queue_id: page_params.queue_id,
                               status_inquiries: _.keys(that._requests)};
                request.success = function (resp) {
                  that._is_authenticated = true;
                  that._is_reconnecting = false;
                  that._reconnect_initiation_time = null;
                  that._connection_failures = 0;
                  var resend_queue = [];
                  _.each(resp.status_inquiries, function (status, id) {
                    if (status.status === 'complete') {
                        that._process_response(id, status.response);
                    } else if (status.status === 'received') {
                        that._update_request_state(id, 'sent');
                    } else if (status.status === 'not_received') {
                        resend_queue.push(id);
                    }
                  });
                  resend_queue.sort(that._req_id_sorter);
                  _.each(resend_queue, function (id) {
                      that._resend(id);
                  });
                };
                request.error = function (type, resp) {
                  blueslip.info("Could not authenticate with server: " + resp.msg);
                  that._connection_failures += 1;
                  that._try_to_reconnect({reason: 'auth_fail',
                                          wait_time: that._reconnect_wait_time()});
                };
                that._save_request(request);
                that._do_send(request);
            });
        };

        sockjs.onmessage = function Socket__sockjs_onmessage(event) {
            if (event.data.type === 'ack') {
                that._process_ack(event.data.req_id);
            } else {
                that._process_response(event.data.req_id, event.data.response);
            }
        };

        sockjs.onheartbeat = function Socket__sockjs_onheartbeat() {
            if (that._heartbeat_timeout_id !== null) {
                clearTimeout(that._heartbeat_timeout_id);
                that._heartbeat_timeout_id = null;
            }
            that._heartbeat_timeout_id = setTimeout(function () {
                that._heartbeat_timeout_id = null;
                blueslip.info("Missed too many hearbeats");
                that._try_to_reconnect({reason: 'no_heartbeat'});
            }, 60000);
        };

        sockjs.onclose = function Socket__sockjs_onclose(event) {
            if (that._is_unloading) {
                return;
            }
            // We've failed to handshake, but notify that the attempt finished
            $(document).trigger($.Event('websocket_postopen.zulip', {}));

            blueslip.info("SockJS connection lost.  Attempting to reconnect soon."
                          + " (" + event.code.toString() + ", " + event.reason + ")");
            that._connection_failures += 1;
            that._is_reconnecting = false;
            // We don't need to specify a reason because the Socket is already closed
            that._try_to_reconnect({wait_time: that._reconnect_wait_time()});
        };
    },

    _reconnect_wait_time: function Socket__reconnect_wait_time() {
        if (this._connection_failures === 1) {
            // We specify a non-zero timeout here so that we don't try to
            // immediately reconnect when the page is refreshing
            return 30;
        }
        return Math.min(90, Math.exp(this._connection_failures/2)) * 1000;
    },

    _try_to_reconnect: function Socket__try_to_reconnect(opts) {
        opts = _.extend({wait_time: 0, reason: 'none_given'}, opts);
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

        // Cancel any pending auth requests and any timeouts for ACKs
        _.each(this._requests, function (val, key) {
            if (val.ack_timeout_id !== null) {
                clearTimeout(val.ack_timeout_id);
                val.ack_timeout_id = null;
            }

            if (val.type === 'auth') {
                that._remove_request(key);
            }
        });

        this._is_open = false;
        this._is_authenticated = false;
        this._is_reconnecting = true;
        this._reconnect_initiation_time = now;
        // This is a little weird because we're also called from the SockJS
        // onclose handler.  Fortunately, close() does nothing on an
        // already-closed SockJS object.  However, we do have to check that
        // this._sockjs isn't undefined since it's not created immediately
        // when running under the test suite.
        if (this._sockjs !== undefined) {
            var close_reason = CLOSE_REASONS[opts.reason];
            this._sockjs.close(close_reason.code, close_reason.msg);
        }

        this._reconnect_timeout_id = setTimeout(function () {
            that._reconnect_timeout_id = null;
            blueslip.info("Attempting socket reconnect.");
            that._create_sockjs_object();
        }, opts.wait_time);
    },

    _localstorage_requests: function Socket__localstorage_requests() {
        if (!localstorage.supported()) {
            return {};
        }
        return JSON.parse(window.localStorage[this._localstorage_requests_key] || "{}");
    },

    _save_localstorage_requests: function Socket__save_localstorage_requests() {
        if (!localstorage.supported()) {
            return;
        }

        // Auth requests are always session-specific, so don't store them for later
        var non_auth_reqs = {};
        _.each(this._requests, function (val, key) {
            if (val.type !== 'auth') {
                non_auth_reqs[key] = val;
            }
        });

        try {
            window.localStorage[this._localstorage_requests_key] = JSON.stringify(non_auth_reqs);
        } catch (e) {
            // We can't catch a specific exception type, because browsers return different types
            // for out of space errors. See http://chrisberkhout.com/blog/localstorage-errors/ for
            // more details.
            blueslip.warn("Failed to save to local storage, caught exception when saving " + e);
        }
    },

    _save_request: function Socket__save_request(request) {
        this._requests[request.req_id] = request;

        if (!localstorage.supported()) {
            return;
        }

        this._save_localstorage_requests();
    },

    _remove_request: function Socket__remove_request(req_id) {
        delete this._requests[req_id];

        if (!localstorage.supported()) {
            return;
        }

        this._save_localstorage_requests();

    },

    _update_request_state: function Socket__update_request_state(req_id, state) {
        this._requests[req_id].state = state;

        if (!localstorage.supported()) {
            return;
        }

        this._save_localstorage_requests();
    },
};

return Socket;
}());

if (typeof module !== 'undefined') {
    module.exports = Socket;
}
