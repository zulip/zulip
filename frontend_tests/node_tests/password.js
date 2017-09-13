zrequire('zxcvbn', 'node_modules/zxcvbn/dist/zxcvbn');
zrequire('common');

set_global('i18n', global.stub_i18n);

(function test_basics() {
    var accepted;
    var password;
    var warning;
    var crack_time_value;

    var crack_time = (function () {
        var self = {};

        self.text = function (arg) {
            self.display = arg;
            return self;
        };

        self.attr = function (arg1, arg2) {
            self.title = arg2;
            return self;
        };

        return self;
    }());

    var score = (function () {
        var self = {};

        self.text = function (pw_score) {
            self.pw_score = pw_score;
            return self;
        };

        self.removeClass = function (arg) {
            assert.equal(arg, 'text-success text-error');
            return self;
        };

        self.addClass = function (arg) {
            self.added_class = arg;
            return self;
        };

        return self;
    }());

    var bar = (function () {
        var self = {};

        self.width = function (width) {
            self.w = width;
            return self;
        };

        self.removeClass = function (arg) {
            assert.equal(arg, 'bar-success bar-danger');
            return self;
        };

        self.addClass = function (arg) {
            self.added_class = arg;
            return self;
        };

        return self;
    }());

    function password_field(min_length, min_guesses) {
        var self = {};

        self.data = function (field) {
            if (field === 'minLength') {
                return min_length;
            } else if (field === 'minGuesses') {
                return min_guesses;
            }
        };

        return self;
    }

    password = 'z!X4@S_&';
    accepted = common.password_quality(password, bar, score, password_field(10, 80000));
    assert(!accepted);
    assert.equal(bar.w, '39.7%');
    assert.equal(bar.added_class, 'bar-danger');
    assert.equal(score.pw_score, "translated: Medium");
    assert.equal(score.added_class, 'text-error');
    warning = common.password_warning(password, password_field(10));
    assert.equal(warning, 'translated: Password should be at least 10 characters long');
    crack_time_value = common.password_crack_time(password, crack_time);
    assert.equal(crack_time_value, '3 hours');
    assert.equal(crack_time.display, 'translated: Crack time: 3 hours');
    assert.equal(crack_time.title, 'translated: This password can be cracked in 3 hours.');

    password = 'foo';
    accepted = common.password_quality(password, bar, score, password_field(2, 200));
    assert(accepted);
    assert.equal(bar.w, '10.390277164940581%');
    assert.equal(bar.added_class, 'bar-success');
    assert.equal(score.pw_score, "translated: Very weak");
    assert.equal(score.added_class, 'text-success');
    warning = common.password_warning(password, password_field(2));
    assert.equal(warning, 'translated: Password is too weak. Add another word or two. Uncommon words are better.');
    crack_time_value = common.password_crack_time(password, crack_time);
    assert.equal(crack_time_value, 'less than a second');
    assert.equal(crack_time.display, 'translated: Crack time: less than a second');
    assert.equal(crack_time.title, 'translated: This password can be cracked in less than a second.');

    password = 'aaaaaaaa';
    accepted = common.password_quality(password, bar, score, password_field(6, 1e100));
    assert(!accepted);
    assert.equal(bar.added_class, 'bar-danger');
    assert.equal(score.pw_score, "translated: Very weak");
    assert.equal(score.added_class, 'text-error');
    warning = common.password_warning(password, password_field(6));
    assert.equal(warning, 'translated: Repeats like "aaa" are easy to guess Add another word or two. Uncommon words are better.,Avoid repeated words and characters');
    crack_time_value = common.password_crack_time(password, crack_time);
    assert.equal(crack_time_value, 'less than a second');
    assert.equal(crack_time.display, 'translated: Crack time: less than a second');
    assert.equal(crack_time.title, 'translated: This password can be cracked in less than a second.');

    delete global.zxcvbn;
    password = 'aaaaaaaa';
    accepted = common.password_quality(password, bar, score, password_field(6, 1e100));
    assert(accepted === undefined);
    warning = common.password_warning(password, password_field(6));
    assert(warning === undefined);
    crack_time_value = common.password_crack_time(password, crack_time);
    assert(crack_time_value === undefined);
}());
