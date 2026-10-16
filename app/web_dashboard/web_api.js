// Browser fallback for the pywebview bridge.
//
// When the hub is opened in a normal browser there is no window.pywebview, so
// every api call is proxied to the backend over HTTP (/api/<method>).
//
// "Is there a bridge?" cannot be answered here, though: this runs from <head>,
// and the desktop app injects its real bridge *afterwards*.  Deciding now would
// install the fallback in the app too -- and `__web` is what the hub uses to
// decide whether to poll /api/logs, so the app would then show every log line
// twice, once over evaluate_js and once over that poll.  The flag is cleared
// the moment the real bridge arrives instead.
(function () {
    if (window.pywebview && window.pywebview.api) { return; }
    var fallbackApi = new Proxy({}, {
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
    });
    var fallback = { api: fallbackApi };
    window.pywebview = fallback;

    // pywebview either replaces this object or fills its api in; only the
    // second leaves the fallback in place.  Either signal means a real bridge
    // arrived, and in that case `__web` must never be set: the hub polls
    // /api/logs while it is, which in the app would show every log line twice
    // -- once pushed over evaluate_js and once pulled from that poll.
    //
    // So the flag is claimed last, once both signals have had their chance,
    // rather than up front and revoked later; revoking still leaves a window
    // in which the first lines are delivered both ways.
    function claimWebMode() {
        if (window.pywebview !== fallback) { return; }    // replaced outright
        if (window.pywebview.api !== fallbackApi) { return; }  // filled in place
        fallback.__web = true;                            // genuinely a browser
    }
    window.addEventListener('pywebviewready', claimWebMode);
    document.addEventListener('DOMContentLoaded', claimWebMode);
})();
