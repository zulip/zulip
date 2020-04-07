/* eslint-env browser */

// PhantomJS doesn’t support new DOMParser().parseFromString(…, "text/html").
var real_parseFromString = DOMParser.prototype.parseFromString;
DOMParser.prototype.parseFromString = function (string, type) {
    if (type === "text/html") {
        var doc = document.implementation.createHTMLDocument("");
        doc.documentElement.innerHTML = string;
        return doc;
    }
    return real_parseFromString.apply(this, arguments);
};
