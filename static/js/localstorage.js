var localstorage = (function () {

var exports = {};

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
