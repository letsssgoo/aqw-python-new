// Browser fallback for the pywebview bridge.
//
// When the hub is opened in a normal browser there is no window.pywebview, so
// every api call is proxied to the backend over HTTP (/api/<method>).  In the
// desktop app the real bridge already exists and this does nothing.
(function () {
    if (window.pywebview && window.pywebview.api) { return; }
    window.pywebview = {
        __web: true,
        api: new Proxy({}, {
            get: function (_target, name) {
                return function () {
                    var args = Array.prototype.slice.call(arguments);
                    return fetch('/api/' + encodeURIComponent(String(name)), {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ args: args })
                    }).then(function (r) { return r.json(); })
                      .catch(function () { return null; });
                };
            }
        })
    };
})();
