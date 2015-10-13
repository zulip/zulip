(function() {
    var elem = document.createElement('div');
    elem.setAttribute('id', 'include2');
    elem.appendChild(document.createTextNode('include2'));
    document.querySelector('body').appendChild(elem);
})();
