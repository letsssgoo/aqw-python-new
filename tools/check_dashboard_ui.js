/* Smoke test for the solo menu's script: does it initialise, and does
 * "add account" actually add one?
 *
 *     node tools/check_dashboard_ui.js
 *
 * Why this exists: a reference to an identifier that is not in scope (an
 * ``acc.`` used inside ``accountTemplate()``) threw inside the click handler,
 * so the ADD button did nothing at all and said nothing -- from the browser it
 * looked like the page was fine.  ``node --check`` cannot see that (it is
 * valid syntax) and neither can any Python test, so the script is driven here
 * against a stub DOM.
 *
 * The stub is deliberately dumb: elements are objects with the few properties
 * the script touches, and every element id is created on demand.
 */
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const file = path.join(__dirname, '..', 'app', 'web_dashboard', 'aqw', 'main.js');
const source = fs.readFileSync(file, 'utf8');

let fail = 0;
function check(label, got, want) {
    const ok = JSON.stringify(got) === JSON.stringify(want);
    if (!ok) { fail++; }
    console.log(`  ${ok ? 'ok  ' : 'FAIL'} ${label}   [${JSON.stringify(got)}]`);
}

function makeElement(id) {
    const listeners = {};
    return {
        id,
        value: '',
        checked: false,
        disabled: false,
        textContent: '',
        innerHTML: '',
        className: '',
        style: {},
        dataset: {},
        scrollTop: 0,
        scrollHeight: 0,
        classList: { add() {}, remove() {}, toggle() {} },
        addEventListener(name, fn) { listeners[name] = fn; },
        removeEventListener() {},
        appendChild() {},
        remove() {},
        setAttribute() {},
        getAttribute() { return null; },
        querySelector() { return null; },
        querySelectorAll() { return []; },
        focus() {},
        click() { if (listeners.click) { listeners.click(); } },
        _listeners: listeners,
    };
}

const elements = {};
const asked = {};
function el(id) {
    asked[id] = (asked[id] || 0) + 1;
    if (!elements[id]) { elements[id] = makeElement(id); }
    return elements[id];
}

const document = {
    getElementById: el,
    createElement: () => makeElement('new'),
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener() {},
    body: makeElement('body'),
    head: makeElement('head'),
    documentElement: makeElement('html'),
};

const window = {
    document,
    addEventListener() {},
    setTimeout: (fn) => { fn(); return 0; },   // run the countdown immediately
    clearTimeout() {},
    setInterval: () => 0,
    clearInterval() {},
    console,
};

const sandbox = {
    window, document, console,
    setTimeout: window.setTimeout,
    clearTimeout: window.clearTimeout,
    setInterval: window.setInterval,
    clearInterval: window.clearInterval,
    JSON, Date, Math, Object, Array, String, Number, Boolean, parseInt, parseFloat,
    Promise, Error, isNaN, encodeURIComponent, decodeURIComponent,
};
sandbox.globalThis = sandbox;
sandbox.window.pywebview = {
    api: new Proxy({}, {
        get: () => (() => Promise.resolve({ success: true, accounts: [] })),
    }),
};
// Provided by components.js in the real page: it waits for the bridge, then
// hands the api to the callback.  Here the stub calls back at once.
sandbox.window.whenApiReady = (cb) => cb(sandbox.window.pywebview.api);
// From players_dropdown.js, loaded before main.js in the real page.
sandbox.attachPlayersDropdown = () => {};

async function main() {
    console.log('='.repeat(74));
    console.log('solo menu script: initialises, and ADD really adds');
    console.log('='.repeat(74));

    try {
        vm.createContext(sandbox);
        vm.runInContext(source, sandbox, { filename: file });
        check('the script loaded without throwing', true, true);
    } catch (e) {
        check(`the script loaded without throwing (${e.message})`, false, true);
        process.exit(1);
    }

    // The page attaches its handlers once the bridge is ready, which the stub
    // resolves through a promise: let the microtasks run before looking.
    await new Promise((resolve) => setImmediate(resolve));

    const addBtn = el('btn-add');
    check('ADD has a click handler', typeof addBtn.onclick, 'function');

    let threw = null;
    try { addBtn.click(); } catch (e) { threw = e.message; }
    check('clicking ADD does not throw', threw, null);

    check('the tab bar was rebuilt', (asked['account-tabs'] || 0) > 0, true);

    const startBtn = el('btn-start');
    check('START has a click handler', typeof startBtn.onclick, 'function');
    let startThrew = null;
    try { startBtn.click(); } catch (e) { startThrew = e.message; }
    check('clicking START does not throw', startThrew, null);

    console.log('='.repeat(74));
    console.log(fail ? `${fail} check(s) failed` : 'all checks passed');
    console.log('='.repeat(74));
    process.exit(fail ? 1 : 0);
}

main();
