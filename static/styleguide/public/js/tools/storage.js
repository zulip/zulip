var storage = (function () {
    var VERSION = "v1";

    var funcs = {
        get: function (version) {
            var store = window.localStorage.getItem("styleguide-storage");

            try {
                if (store) {
                    store = JSON.parse(store);
                } else {
                    store = this.create(version || VERSION);
                }
            } catch (e) {
                store = this.create(version || VERSION);
            } finally {
                if (version) {
                    return store[version];
                } else {
                    return store;
                }
            }
        },
        set: function (data) {
            return window.localStorage.setItem("styleguide-storage", JSON.stringify(data));
        },
        apply: function (version, data) {
            var store = this.get();

            if (!store[version]) {
                store[version] = {};
            }

            for (var x in data) {
                store[version][x] = data[x];
            }

            return this.set(store);
        },
        create: function (version) {
            var store = {};
            store[version] = {};

            window.localStorage.setItem("styleguide-storage", this.set(version, store));

            return store;
        }
    };

    return {
        get: function (version) {
            return funcs.get(version || VERSION);
        },
        set: function (data) {
            funcs.apply(VERSION, data);

            return this;
        }
    };
}());
