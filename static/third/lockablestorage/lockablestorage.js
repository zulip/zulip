/**
Copyright (c) 2012, Benjamin Dumke-von der Ehe

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions
of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
*/

/*
 LockableStorage.lock(key, lockAquiredCallback)
*/
(function () {

    function now() {
        return new Date().getTime();
    }
    
    function someNumber() {
        return Math.random() * 1000000000 | 0;
    }

    var myId = now() + ":" + someNumber();
        
    function getter(lskey) {
        return function () {
            var value = localStorage[lskey];
            if (!value)
                return null;
            
            var splitted = value.split(/\|/);
            if (parseInt(splitted[1]) < now()) {
                return null;
            }
            return splitted[0];
        }
    }
    
    function _mutexTransaction(key, callback, synchronous) {
        var xKey = key + "__MUTEX_x",
            yKey = key + "__MUTEX_y",
            getY = getter(yKey);

        function criticalSection() {
            try {
                callback();
            } finally {
                localStorage.removeItem(yKey);
            }
        }
        
        localStorage[xKey] = myId;
        if (getY()) {
            if (!synchronous)
                setTimeout(function () { _mutexTransaction(key, callback); }, 0);
            return false;
        }
        localStorage[yKey] = myId + "|" + (now() + 40);
        
        if (localStorage[xKey] !== myId) {
            if (!synchronous) {
                setTimeout(function () {
                    if (getY() !== myId) {
                        setTimeout(function () { _mutexTransaction(key, callback); }, 0);
                    } else {
                        criticalSection();
                    }
                }, 50)
            }
            return false;
        } else {
            criticalSection();
            return true;
        }
    }
    
    function lockImpl(key, callback, maxDuration, synchronous) {

        maxDuration = maxDuration || 5000;
        
        var mutexKey = key + "__MUTEX",
            getMutex = getter(mutexKey),
            mutexValue = myId + ":" + someNumber() + "|" + (now() + maxDuration);
            
        function restart () {
            setTimeout(function () { lockImpl(key, callback, maxDuration); }, 10);
        }
        
        if (getMutex()) {
            if (!synchronous)
                restart();
            return false;
        }
        
        var aquiredSynchronously = _mutexTransaction(key, function () {
            if (getMutex()) {
                if (!synchronous)
                    restart();
                return false;
            }
            localStorage[mutexKey] = mutexValue;
            if (!synchronous)
                setTimeout(mutexAquired, 0)
        }, synchronous);
        
        if (synchronous && aquiredSynchronously) {
            mutexAquired();
            return true;
        }
        return false;
        function mutexAquired() {
            try {
                callback();
            } finally {
                _mutexTransaction(key, function () {
                    if (localStorage[mutexKey] !== mutexValue)
                        throw key + " was locked by a different process while I held the lock"
                
                    localStorage.removeItem(mutexKey);
                });
            }
        }
        
    }
    
    window.LockableStorage = {
        lock: function (key, callback, maxDuration) { lockImpl(key, callback, maxDuration, false) },
        trySyncLock: function (key, callback, maxDuration) { return lockImpl(key, callback, maxDuration, true) }
    };
})();
