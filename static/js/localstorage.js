var localstorage = (function () {

var ls = {
    // parse JSON without throwing an error.
    parseJSON: function (str) {
        try {
            return JSON.parse(str);
        } catch (err) {
            return;
        }
    },

    // check if the datestamp is from before now and if so return true.
    isExpired: function (stamp) {
        return new Date(stamp) < new Date();
    },

    // return the localStorage key that is bound to a version of a key.
    formGetter: function (version, name) {
        return "ls__" + version + "__" + name;
    },

    // create a formData object to put in the data, a signature that it was
    // created with this library, and when it expires (if ever).
    formData: function (data, expires) {
        return {
            data: data,
            __valid: true,
            expires: new Date().getTime() + expires,
        };
    },

    getData: function (version, name) {
        var key = this.formGetter(version, name);
        var data = localStorage.getItem(key);
        data = ls.parseJSON(data);

        if (data) {
            if (data.__valid) {
                // JSON forms of data with `Infinity` turns into `null`,
                // so if null then it hasn't expired since nothing was specified.
                if (!ls.isExpired(data.expires) || data.expires === null) {
                    return data;
                }
            }
        }
    },

    // set the wrapped version of the data into localStorage.
    setData: function (version, name, data, expires) {
        var key = this.formGetter(version, name);
        var val = this.formData(data, expires);

        localStorage.setItem(key, JSON.stringify(val));
    },

    // remove the key from localStorage and from memory.
    removeData: function (version, name) {
        var key = this.formGetter(version, name);

        localStorage.removeItem(key);
    },

    // Remove keys which match a regex.
    removeDataRegex: function (version, regex) {
        var key_regex = new RegExp(this.formGetter(version, regex));
        var keys = Object.keys(localStorage).filter(function (key) {
            return key_regex.test(key);
        });

        keys.forEach(function (key) {
            localStorage.removeItem(key);
        });
    },

    // migrate from an older version of a data src to a newer one with a
    // specified callback function.
    migrate: function (name, v1, v2, callback) {
        var old = this.getData(v1, name);
        this.removeData(v1, name);

        if (old && old.__valid) {
            var data = callback(old.data);
            this.setData(v2, name, data, Infinity);

            return data;
        }
    },
};

// return a new function instance that has instance-scoped variables.
var exports = function () {
    var _data = {
        VERSION: 1,
        expires: Infinity,
        expiresIsGlobal: false,
    };

    var prototype = {
        // `expires` should be a Number that represents the number of ms from
        // now that this should expire in.
        // this allows for it to either be set only once or permanently.
        setExpiry: function (expires, isGlobal) {
            _data.expires = expires;
            _data.expiresIsGlobal = isGlobal || false;

            return this;
        },

        get: function (name) {
            var data = ls.getData(_data.VERSION, name);

            if (data) {
                return data.data;
            }
        },

        set: function (name, data) {
            if (typeof _data.VERSION !== "undefined") {
                ls.setData(_data.VERSION, name, data, _data.expires);

                // if the expires attribute was not set as a global, then
                // make sure to return it back to Infinity to not impose
                // constraints on the next key.
                if (!_data.expiresIsGlobal) {
                    _data.expires = Infinity;
                }

                return true;
            }

            return false;
        },

        // remove a key with a given version.
        remove: function (name) {
            ls.removeData(_data.VERSION, name);
        },

        // Remove keys which match the pattern given by name.
        removeRegex: function (name) {
            ls.removeDataRegex(_data.VERSION, name);
        },

        migrate: function (name, v1, v2, callback) {
            return ls.migrate(name, v1, v2, callback);
        },
    };

    // set a new master version for the LocalStorage instance.
    Object.defineProperty(prototype, "version", {
        get: function () {
            return _data.VERSION;
        },
        set: function (version) {
            _data.VERSION = version;

            return prototype;
        },
    });

    return prototype;
};

var warned_of_localstorage = false;

exports.supported = function supports_localstorage() {
    try {
        return window.hasOwnProperty('localStorage') && window.localStorage !== null;
    } catch (e) {
        if (!warned_of_localstorage) {
            blueslip.error("Client browser does not support local storage, will lose socket message on reload");
            warned_of_localstorage = true;
        }
        return false;
    }
};

return exports;
}());

if (typeof module !== 'undefined') {
    module.exports = localstorage;
}
