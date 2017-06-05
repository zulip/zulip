var Router = (function () {
    var funcs = {
        // enums to describe the types that a particular path segment can be:
        // - PATH: hardcoded segment such as /users/.
        // - VARIABLE: variable in path such as /:id/, where ID can be anything
        //             in the expression /[^\/]/.
        E: {
            PATH: 0,
            VARIABLE: 1,
            ALL: 2,
        },

        // this is a method for parsing a path into segments.
        // path: A string path of the hash component.
        // this returns an array of dictionaries that have the keys "type" and
        // "component".
        // in the case of a path, the component is the hardcoded path, whereas
        // in the case of a variable it is either the key for the segment (if it
        // is the defined route), or the value (if it is the accessed route).
        // Example:
        // route:    /users/:id => { type: 1, component: "id" }
        // accessed: /users/230 => { type: 0, component: "230" }
        parse: function (path) {
            // remove leading and trailing slashes.
            var _path = path
                .replace(/^#/, "")
                .replace(/^\/|\/$/, "");

            // split the path by '/', map over and test whether the segments
            // are declarative variables or hardcoded.
            _path = _path.split(/\//).map(function (component) {
                var type;
                if (/^:/.test(component)) {
                    type = funcs.E.VARIABLE;
                } else if (/^\*/.test(component)) {
                    type = funcs.E.ALL;
                } else {
                    type = funcs.E.PATH;
                }

                return { type: type, component: component };
            });

            return _path;
        },

        // where route = stored route, path = current hash.
        // this will take two paths and compare them -- one being a base route
        // and the other being a user-accessed path.
        compare: function (route, path) {
            var map = {};

            var len = Math.max(path.length, route.length);

            for (var x = 0; x < len; x += 1) {
                // if the route exists and the type is a path (hardcoded), then
                // check if the path exists and is the same to continue.
                if (route[x] && route[x].type === funcs.E.PATH &&
                    path[x] && path[x].component === route[x].component) {
                    continue;
                // otherwise if the route exists and is a variable, check if the
                // path exists. If so, continue.
                } else if (route[x] && route[x].type === funcs.E.VARIABLE && path[x]) {
                    // if there is a variable in the route, then make a key of the
                    // route segment and a value of the user-accessed path's segment.
                    map[route[x].component.replace(/^:/, "")] = path[x].component;
                    continue;
                // otherwise, this user-accessed path is not going to work with
                // this route.
                } else if (route[x] && route[x].type === funcs.E.ALL && path[x]) {
                    // if the * is not at the end of the route, it is just a
                    // segment * (similar to :id, but without variable capture).
                    // however if it is at the end of a route, it will capture
                    // up the rest of the string.
                    if (x < route.length - 1) {
                        // just check for any valid match.
                        continue;
                    } else {
                        map.__ALL = path.slice(x).map(function (o) {
                            return o.component;
                        }).join("/");
                        break;
                    }
                } else {
                    return false;
                }
            }

            return map;
        },

        // this works similarly to express middleware in that when middleware
        // should continue, it should execute the `run()` function inside the
        // function scope to reach either the next piece of middleware or the
        // route if there is no middleware left.
        run_middleware: function (data, middleware, callback) {
            var counter = 0;

            // this is a function to successfully run when middleware should
            // continue on to the next step.
            var run = function () {
                // if there is no more middleware, run the actual route.
                if (counter === middleware.length) {
                    callback();
                // otherwise, run the next piece of middleware and expect for
                // the middleware to call the run function which has access to
                // the `counter` variable.
                } else {
                    counter += 1;
                    middleware[counter - 1](data, run);
                }
            };

            run();
        },

        // the `this` arg should be replaced with the prototype's `this`.
        resolve_hashchange: function (e) {
            // the `window.location.hash` isn't actually the hash necessarily currently
            // in the browser. This happens when you change the hash multiple times
            // successively. To truly capture the state of the hashchange, we need to
            // grab the `e.newURL` property.

            var hash = (function (url) {
                var a = document.createElement("a");
                a.href = url;

                return a.hash;
            }(e.newURL));

            this.history.push(hash);

            var path = funcs.parse(hash);

            // e: the event of the hashchange.
            // x: the
            var run_route = function (e, route) {
                // transmit original event and `this` arg.
                route.callback.call(this, e);
            };

            // iterate through each of the routes to find a match.
            for (var x = 0; x < this.routes.length; x += 1) {
                // check if the route is valid.
                // this also will return a map of valid key/value pairs.
                var map = funcs.compare(this.routes[x].route, path);
                if (map) {
                    // set map inside the hashchange event to deliver in the callback.
                    e.params = map;
                    e.hash = hash;

                    // if there is an ending `__ALL` segment, we should record it
                    // in the `endHash` method.
                    if (e.params.__ALL) {
                        e.endHash = e.params.__ALL;
                        delete e.params.__ALL;
                    }

                    funcs.run_middleware(
                        e, this.middleware, run_route.bind(this, e, this.routes[x])
                    );

                    return;
                }
            }

            funcs.run_middleware(e, this.middleware, function () {});
        },
    };

    var Router = function (win) {
        this.routes = [];
        this.middleware = [];
        this.history = [];

        if (win) {
            this.__window__ = win;
        } else if (typeof window !== "undefined") {
            this.__window__ = window;
        }

        // add with `addEventListener` to not disrupt other possible events bound
        // to `onhashchange`.
        this.__window__.addEventListener("hashchange", funcs.resolve_hashchange.bind(this));

        return this;
    };

    Router.prototype = {
        // allow for users to access the parse function to parse on their own.
        parse: funcs.parse,

        matches: function (route, path) {
            return funcs.compare(funcs.parse(route), funcs.parse(path));
        },

        // set a new route that runs a particular callback when successfully hit.
        add: function (route, callback) {
            if (Array.isArray(route)) {
                route.forEach(function (r) {
                    this.add(r, callback);
                }.bind(this));

                return;
            }

            this.routes.push({
                route: funcs.parse(route),
                callback: callback,
            });
        },
        use: function (callback) {
            this.middleware.push(callback);
        },
        init: function () {
            funcs.resolve_hashchange.call(this, {
                newURL: this.__window__.location.href,
                initial_load: true,
            });
            return this;
        },

        type: funcs.E,
    };

    return Router;
}());

if (typeof module !== "undefined") {
    module.exports = Router;
}
