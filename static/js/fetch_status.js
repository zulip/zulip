var FetchStatus = function () {

    var self = {};

    var loading_older = false;
    var loading_newer = false;
    var found_oldest = false;
    var found_newest = false;

    self.start_initial_narrow = function () {
        loading_newer = true;
        loading_older = true;
    };

    self.finish_initial_narrow = function (opts) {
        loading_newer = false;
        loading_older = false;
        found_oldest = opts.found_oldest;
        found_newest = opts.found_newest;
    };

    self.start_older_batch = function () {
        loading_older = true;
    };

    self.finish_older_batch = function (opts) {
        loading_older = false;
        found_oldest = opts.found_oldest;
    };

    self.can_load_older_messages = function () {
        return !loading_older && !found_oldest;
    };

    self.start_newer_batch = function () {
        loading_newer = true;
    };

    self.finish_newer_batch = function (opts) {
        loading_newer = false;
        found_newest = opts.found_newest;
    };

    self.can_load_newer_messages = function () {
        return !loading_newer && !found_newest;
    };

    return self;

};
if (typeof module !== 'undefined') {
    module.exports = FetchStatus;
}
