(function() {
    var elem = document.createElement('div');
    elem.setAttribute('id', 'include1');
    elem.appendChild(document.createTextNode('include1'));
    document.querySelector('body').appendChild(elem);
})();
