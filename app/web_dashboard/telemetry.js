/* Live telemetry modal — one implementation for every dashboard that runs bots.
 *
 *   AqwTelemetry.open({
 *       key: 'AccountName',                 // account to show first
 *       accounts: [{key, label}],           // optional account switcher
 *       get: (key) => Promise<telemetry>,   // required, 1s poll while open
 *       pickup: (key, itemId) => Promise    // optional, enables "Pick Up"
 *   });
 *
 * The payload is whatever the backend's `build_telemetry` returns.  Polling
 * stops as soon as the modal closes, so a page that never opens it pays
 * nothing.  Styles live in telemetry.css, scoped to #aqw-tel-modal.
 */
(function () {
    'use strict';

    var POLL_MS = 1000;
    var root = null;
    var timer = null;
    var current = '';
    var options = null;

    function esc(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    }

    function node(name) { return root ? root.querySelector('[data-tel="' + name + '"]') : null; }

    function setText(name, value) {
        var el = node(name);
        if (el) { el.textContent = value; }
    }

    function markup() {
        return '' +
            '<div id="aqw-tel-modal" class="hidden">' +
            '  <div class="tel-modal">' +
            '    <button type="button" class="tel-close" data-tel="close" title="Close">&times;</button>' +
            '    <div class="tel-head">' +
            '      <div>' +
            '        <span class="tel-tag">Live Telemetry</span>' +
            '        <div class="tel-title-row">' +
            '          <h3 class="tel-title" data-tel="username">Account</h3>' +
            '          <span class="tel-class" data-tel="class">-</span>' +
            '          <span class="tel-status offline" data-tel="status"><span class="tel-dot"></span><span data-tel="status-text">Offline</span></span>' +
            '          <span class="tel-combat" data-tel="combat">Idle</span>' +
            '        </div>' +
            '        <p class="tel-sub">Real-time state, active auras, and dropped loot inspector</p>' +
            '      </div>' +
            '      <div class="tel-switcher" data-tel="switcher">' +
            '        <label>Switch account:</label>' +
            '        <select data-tel="select"></select>' +
            '      </div>' +
            '    </div>' +
            '    <div class="tel-tabs">' +
            '      <button type="button" class="tel-tab active" data-tab="state">Player &amp; Target State</button>' +
            '      <button type="button" class="tel-tab" data-tab="auras">Active Auras <span class="tel-badge" data-tel="auras-count">0</span></button>' +
            '      <button type="button" class="tel-tab" data-tab="drops">Dropped Items <span class="tel-badge" data-tel="drops-count">0</span></button>' +
            '    </div>' +
            '    <div class="tel-body">' +
            '      <div class="tel-pane active" data-pane="state">' +
            '        <div class="tel-grid">' +
            '          <div class="tel-card">' +
            '            <div class="tel-card-title">Player Vitals</div>' +
            '            <div class="tel-vital"><div class="tel-vital-head"><b>HP</b><span data-tel="hp-text">0 / 0</span></div><div class="tel-bar"><div class="tel-bar-fill hp" data-tel="hp-bar"></div></div></div>' +
            '            <div class="tel-vital"><div class="tel-vital-head"><b>MP</b><span data-tel="mp-text">0 / 0</span></div><div class="tel-bar"><div class="tel-bar-fill mp" data-tel="mp-bar"></div></div></div>' +
            '            <div class="tel-stats">' +
            '              <div class="tel-stat"><span class="tel-stat-label">Location</span><span class="tel-stat-value" data-tel="map">-</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Cell / Pad</span><span class="tel-stat-value" data-tel="cell-pad">-</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Coordinates</span><span class="tel-stat-value" data-tel="coords">0, 0</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Server</span><span class="tel-stat-value" data-tel="server">-</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Gold</span><span class="tel-stat-value gold" data-tel="gold">0</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Farmed Gold</span><span class="tel-stat-value gold" data-tel="gold-farmed">+0</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Farmed EXP</span><span class="tel-stat-value exp" data-tel="exp-farmed">+0</span></div>' +
            '              <div class="tel-stat"><span class="tel-stat-label">Haste / CD Red.</span><span class="tel-stat-value" data-tel="cd">0%</span></div>' +
            '            </div>' +
            '          </div>' +
            '          <div class="tel-card">' +
            '            <div class="tel-card-title">Current Combat Target</div>' +
            '            <div class="tel-empty" data-tel="target-empty">No target right now.</div>' +
            '            <div class="hidden" data-tel="target">' +
            '              <div class="tel-vital-head"><span class="tel-target-name" data-tel="target-name">-</span><span class="tel-target-map" data-tel="target-map">-</span></div>' +
            '              <div class="tel-bar"><div class="tel-bar-fill enemy" data-tel="target-bar"></div></div>' +
            '              <div class="tel-vital-head" style="margin-top:4px"><span></span><span data-tel="target-hp">0 / 0</span></div>' +
            '              <div class="tel-chips" data-tel="target-auras"></div>' +
            '            </div>' +
            '          </div>' +
            '        </div>' +
            '      </div>' +
            '      <div class="tel-pane" data-pane="auras">' +
            '        <div class="tel-auras" data-tel="auras"></div>' +
            '        <div class="tel-empty" data-tel="auras-empty">No active auras.</div>' +
            '      </div>' +
            '      <div class="tel-pane" data-pane="drops">' +
            '        <div class="tel-drops-head">' +
            '          <span class="tel-muted" data-tel="drops-summary">0 item drop(s) recorded in session</span>' +
            '        </div>' +
            '        <div class="tel-drops-wrap">' +
            '          <table class="tel-drops">' +
            '            <thead><tr><th>Item</th><th>Qty</th><th>Type</th><th>Time</th><th>Status</th><th style="text-align:center">Action</th></tr></thead>' +
            '            <tbody data-tel="drops"></tbody>' +
            '          </table>' +
            '        </div>' +
            '        <div class="tel-empty" data-tel="drops-empty">No drops recorded yet.</div>' +
            '      </div>' +
            '    </div>' +
            '  </div>' +
            '</div>';
    }

    function show(name, visible) {
        var el = node(name);
        if (el) { el.classList.toggle('hidden', !visible); }
    }

    function pct(value, total) {
        if (!total || total <= 0) { return 0; }
        return Math.min(100, Math.max(0, (value / total) * 100));
    }

    function render(data) {
        if (!data) { return; }

        setText('username', data.username || current || 'Account');
        setText('class', data.char_class || '-');

        var status = node('status');
        if (status) {
            var state = 'offline';
            var label = 'Offline';
            if (data.running) {
                if (data.is_dead) { state = 'dead'; label = 'Dead'; }
                else if (data.is_paused) { state = 'paused'; label = 'Paused'; }
                else if (data.is_connected) { state = 'online'; label = 'Serving'; }
                else { state = 'connecting'; label = 'Connecting...'; }
            }
            status.className = 'tel-status ' + state;
            setText('status-text', label);
        }

        var combat = node('combat');
        if (combat) {
            combat.className = 'tel-combat' + (data.is_in_combat ? ' combat' : '');
            combat.textContent = data.is_in_combat ? 'IN COMBAT' : 'PEACEFUL / IDLE';
        }

        var hp = data.hp || 0;
        var maxHp = data.max_hp || 0;
        var hpPct = pct(hp, maxHp);
        var hpBar = node('hp-bar');
        if (hpBar) { hpBar.style.width = hpPct + '%'; }
        setText('hp-text', hp + ' / ' + maxHp + ' (' + Math.round(hpPct) + '%)');

        var mp = data.mp || 0;
        var maxMp = data.max_mp || 0;
        var mpPct = pct(mp, maxMp);
        var mpBar = node('mp-bar');
        if (mpBar) { mpBar.style.width = mpPct + '%'; }
        setText('mp-text', mp + ' / ' + maxMp + ' (' + Math.round(mpPct) + '%)');

        setText('map', data.map || '-');
        setText('cell-pad', (data.cell || '-') + ' / ' + (data.pad || '-'));
        setText('coords', 'X: ' + (data.x || 0) + ', Y: ' + (data.y || 0));
        setText('server', data.server || '-');
        setText('gold', (data.gold || 0).toLocaleString());
        setText('gold-farmed', '+' + (data.gold_farmed || 0).toLocaleString());
        setText('exp-farmed', '+' + (data.exp_farmed || 0).toLocaleString());
        setText('cd', Math.round((data.cd_reduction || 0) * 100) + '%');

        var target = data.target;
        show('target', !!(target && target.name));
        show('target-empty', !(target && target.name));
        if (target && target.name) {
            setText('target-name', target.name);
            setText('target-map', 'MonMapID: ' + (target.map_id == null ? '' : target.map_id));
            var tHp = target.hp || 0;
            var tMax = target.max_hp || 0;
            var tBar = node('target-bar');
            if (tBar) { tBar.style.width = pct(tHp, tMax) + '%'; }
            setText('target-hp', tHp + ' / ' + tMax + ' (' + Math.round(pct(tHp, tMax)) + '%)');
            var chips = node('target-auras');
            if (chips) {
                var debuffs = target.auras || [];
                chips.innerHTML = debuffs.length
                    ? debuffs.map(function (a) {
                        return '<span class="tel-chip">' + esc(a.name) +
                            (a.stacks > 1 ? ' x' + a.stacks : '') +
                            ' (' + (a.remaining || 0) + 's)</span>';
                    }).join('')
                    : '<span class="tel-muted">No target debuffs</span>';
            }
        }

        var auras = data.auras || [];
        setText('auras-count', auras.length);
        show('auras-empty', auras.length === 0);
        var auraBox = node('auras');
        if (auraBox) {
            auraBox.innerHTML = auras.map(function (a) {
                var isBuff = String(a.type || 'buff').toLowerCase() === 'buff';
                var timer = a.remaining > 0 ? a.remaining + 's remaining' : 'Active';
                return '<div class="tel-aura ' + (isBuff ? 'buff' : 'debuff') + '">' +
                    '<div class="tel-aura-head"><span class="tel-aura-name">' + esc(a.name) + '</span>' +
                    (a.stacks > 1 ? '<span class="tel-aura-stacks">x' + a.stacks + '</span>' : '') +
                    '</div>' +
                    '<div class="tel-aura-foot"><span class="tel-aura-type">' + (isBuff ? 'Buff' : 'Debuff') + '</span>' +
                    '<span class="tel-aura-timer">' + esc(timer) + '</span></div>' +
                    (a.spell ? '<div class="tel-aura-spell">From: ' + esc(a.spell) + '</div>' : '') +
                    '</div>';
            }).join('');
        }

        var drops = data.dropped_items || [];
        setText('drops-count', drops.length);
        setText('drops-summary', drops.length + ' item drop(s) recorded in session');
        show('drops-empty', drops.length === 0);
        var tbody = node('drops');
        if (tbody) {
            tbody.innerHTML = drops.map(function (d) {
                var status = d.picked_up
                    ? '<span class="tel-drop-status looted">Looted</span>'
                    : '<span class="tel-drop-status on-ground">On Ground</span>';
                var action = d.picked_up
                    ? '<span class="tel-muted">Done</span>'
                    : '<button type="button" class="tel-pickup" data-id="' + esc(d.item_id) + '">Pick Up</button>';
                return '<tr>' +
                    '<td><div class="tel-drop-name"><span>' + esc(d.item_name) + '</span>' +
                    (d.is_acs ? '<span class="tel-badge-ac">AC</span>' : '') +
                    (d.is_temp ? '<span class="tel-badge-temp">TEMP</span>' : '') +
                    '</div></td>' +
                    '<td>' + (d.qty || 1) + '</td>' +
                    '<td><span class="tel-muted">' + esc(d.s_type || 'Item') + '</span></td>' +
                    '<td><span class="tel-muted">' + esc(d.time || '-') + '</span></td>' +
                    '<td>' + status + '</td>' +
                    '<td style="text-align:center">' + action + '</td>' +
                    '</tr>';
            }).join('');
        }
    }

    function build() {
        if (root) { return root; }
        var holder = document.createElement('div');
        holder.innerHTML = markup();
        root = holder.firstElementChild;
        document.body.appendChild(root);

        root.addEventListener('click', function (e) {
            if (e.target === root || e.target.closest('[data-tel="close"]')) {
                close();
                return;
            }
            var tab = e.target.closest('[data-tab]');
            if (tab) {
                var name = tab.getAttribute('data-tab');
                root.querySelectorAll('[data-tab]').forEach(function (t) {
                    t.classList.toggle('active', t === tab);
                });
                root.querySelectorAll('[data-pane]').forEach(function (p) {
                    p.classList.toggle('active', p.getAttribute('data-pane') === name);
                });
                return;
            }
            var pick = e.target.closest('.tel-pickup');
            if (pick) { pickUp(pick); }
        });

        var select = node('select');
        if (select) {
            select.addEventListener('change', function () {
                current = select.value;
                poll();
            });
        }
        return root;
    }

    function pickUp(button) {
        var picker = options && options.pickup;
        if (!picker) { return; }
        var itemId = button.getAttribute('data-id');
        button.disabled = true;
        button.textContent = 'Picking...';
        Promise.resolve(picker(current, itemId)).then(function (res) {
            if (!res || !res.success) {
                button.disabled = false;
                button.textContent = 'Pick Up';
            }
            poll();
        }).catch(function () {
            button.disabled = false;
            button.textContent = 'Pick Up';
        });
    }

    function poll() {
        var getter = options && options.get;
        if (!current || !getter) { return; }
        Promise.resolve(getter(current)).then(render).catch(function (err) {
            render({
                username: current, running: false, is_connected: false,
                error: (err && err.message) || String(err)
            });
        });
    }

    function start() {
        stop();
        poll();
        timer = setInterval(poll, POLL_MS);
    }

    function stop() {
        if (timer) {
            clearInterval(timer);
            timer = null;
        }
    }

    function close() {
        stop();
        if (root) { root.classList.add('hidden'); }
    }

    function open(opts) {
        options = opts || {};
        current = options.key || '';
        build();

        var select = node('select');
        var switcher = node('switcher');
        var list = options.accounts || [];
        if (select) {
            select.innerHTML = list.map(function (acc) {
                return '<option value="' + esc(acc.key) + '">' + esc(acc.label || acc.key) + '</option>';
            }).join('');
            select.value = current;
        }
        if (switcher) { switcher.style.display = list.length > 1 ? '' : 'none'; }

        setText('username', current || 'Account');
        setText('class', '-');
        var status = node('status');
        if (status) { status.className = 'tel-status offline'; }
        setText('status-text', 'Offline');

        root.classList.remove('hidden');
        start();
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && root && !root.classList.contains('hidden')) {
            close();
        }
    });

    window.AqwTelemetry = { open: open, close: close };
})();
