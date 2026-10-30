(function () {
    // One page for every Ultra V2 fight: the menu entry that opened this iframe
    // decides which ultra it is, and the bridge injected by the hub already
    // binds every call to that id.
    var SLOT_IDS = ['slot1', 'slot2', 'slot3', 'slot4'];
    var form = null;             // the schema the backend sent

    function api() { return window.pywebview && window.pywebview.api; }

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
        });
    }

    function msg(text, ok) {
        var el = document.getElementById('msg');
        if (!el) return;
        el.textContent = text || '';
        el.className = 'cfg-msg' + (text ? (ok ? ' ok' : ' err') : '');
    }

    function field(key) {
        return (form && form.schema || []).filter(function (f) { return f.key === key; })[0];
    }

    // --- composition ------------------------------------------------------
    function fillComposition() {
        var sel = document.getElementById('composition');
        var spec = field('composition');
        if (!spec) return;
        // The composition detail belongs *inside* the option label; the hint
        // line under the dropdown was the thing removed, not this.
        sel.innerHTML = (spec.choices || []).map(function (c) {
            return '<option value="' + esc(c.value) + '">' + esc(c.label) +
                (c.help ? ' \u2014 ' + esc(c.help) : '') + '</option>';
        }).join('');
    }

    function fillRetries() {
        var sel = document.getElementById('retries');
        var spec = field('retries');
        sel.innerHTML = ((spec && spec.choices) || []).map(function (c) {
            return '<option value="' + esc(c.value) + '">' + esc(c.label) + '</option>';
        }).join('');
    }

    // --- panes ------------------------------------------------------------
    function buildSlot(i, sId) {
        var card = document.createElement('div');
        card.className = 'slot-card ' + (i % 2 === 0 ? 'sun-theme' : 'moon-theme');
        card.dataset.slot = sId;
        card.innerHTML =
            '<div class="slot-header" style="display:flex;justify-content:space-between;align-items:center">' +
            '  <div class="slot-title-group" style="display:flex;align-items:center;gap:10px">' +
            '    <div class="slot-icon-box" style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;border-radius:8px;background:rgba(56,189,248,.15);border:1px solid rgba(56,189,248,.3)">' +
            '      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="width:14px;height:14px;color:#38bdf8"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"></path><circle cx="9" cy="7" r="4"></circle></svg>' +
            '    </div>' +
            '    <div style="display:flex;flex-direction:column">' +
            '      <span style="font-size:.88rem;font-weight:700;line-height:1.2">Slot ' + (i + 1) + '</span>' +
            '      <span class="slot-class" style="font-size:.68rem;color:var(--text-secondary,#94a3b8);font-weight:500">&mdash;</span>' +
            '    </div>' +
            '  </div>' +
            '  <div class="status-badge" data-badge>Offline</div>' +
            '</div>' +
            '<div class="slot-body">' +
            '  <div class="slot-inputs-container" style="display:flex;flex-direction:column;gap:10px">' +
            '    <div class="form-group"><label>Player</label><select class="slot-player"></select></div>' +
            '    <div class="form-group"><label>Username</label><input type="text" class="slot-user" placeholder="Username" autocomplete="off"></div>' +
            '    <div class="form-group"><label>Password</label><div class="password-wrapper"><input type="password" class="slot-pass" placeholder="Password" autocomplete="off"></div></div>' +
            '    <div class="slot-status" data-status><span class="pill">idle</span></div>' +
            '  </div>' +
            '</div>';
        attachPlayersDropdown(card.querySelector('.slot-player'), function (user, pass) {
            card.querySelector('.slot-user').value = user;
            card.querySelector('.slot-pass').value = pass;
        });
        return card;
    }

    function applyConfig(config) {
        document.getElementById('server').value = config.server || 'Alteon';
        document.getElementById('room').value = config.room_number || 9099;
        if (config.composition) document.getElementById('composition').value = config.composition;
        if (config.retries) document.getElementById('retries').value = String(config.retries);
        document.getElementById('use-potions').checked = config.use_potions !== false;
        document.getElementById('use-enhancements').checked = config.use_enhancements !== false;
        var slots = config.slots || {};
        SLOT_IDS.forEach(function (sId) {
            var card = document.querySelector('.slot-card[data-slot="' + sId + '"]');
            var s = slots[sId] || {};
            if (s.username) card.querySelector('.slot-user').value = s.username;
            if (s.password) card.querySelector('.slot-pass').value = s.password;
            // The log tabs are labelled by these, and lines are routed by them.
            paneUsers[sId] = s.username || '';
        });
        if (typeof buildLogTabs === 'function') { buildLogTabs(); renderLog(); }
    }

    function collect() {
        var room = parseInt(document.getElementById('room').value || '9099', 10);
        var config = {
            server: document.getElementById('server').value || 'Alteon',
            // One room field: the header's.  A number in the private range is
            // the private map room; anything lower is the public map (0).
            room_number: room,
            private_room: room >= 1001 ? room : 0,
            composition: document.getElementById('composition').value,
            retries: parseInt(document.getElementById('retries').value || '3', 10),
            use_potions: document.getElementById('use-potions').checked,
            use_enhancements: document.getElementById('use-enhancements').checked,
            slots: {}
        };
        SLOT_IDS.forEach(function (sId) {
            var card = document.querySelector('.slot-card[data-slot="' + sId + '"]');
            config.slots[sId] = {
                username: card.querySelector('.slot-user').value.trim(),
                password: card.querySelector('.slot-pass').value
            };
        });
        return config;
    }

    function renderStatus(status) {
        var slots = (status && status.slots) || {};
        var running = !!(status && status.running);
        setButton(running);
        SLOT_IDS.forEach(function (sId) {
            var card = document.querySelector('.slot-card[data-slot="' + sId + '"]');
            if (!card) return;
            var badge = card.querySelector('[data-badge]');
            var el = card.querySelector('[data-status]');
            var s = slots[sId];
            if (!s || !s.running) {
                badge.textContent = 'Offline'; badge.style.color = '';
                el.innerHTML = '<span class="pill">idle</span>'; return;
            }
            badge.textContent = 'Online'; badge.style.color = '#34d399';
            var hp = s.max_hp ? Math.round(s.hp / s.max_hp * 100) : 0;
            var cooldowns = (s.skills || []).map(function (skill) {
                var label = 'S' + (skill.slot === 0 ? 'A' : skill.slot);
                var ready = (skill.ready_in || 0) <= 0;
                return '<span class="pill" style="' +
                    (ready ? 'opacity:.55' : '') + '">' + label + ' ' +
                    (ready ? '✓' : (skill.ready_in / 1000).toFixed(1) + 's') +
                    '</span>';
            }).join(' ');
            el.innerHTML =
                '<span class="pill">' + esc(s.username || '-') + '</span>' +
                '<span class="pill">HP ' + hp + '%</span>' +
                '<span class="pill">MP ' + (s.mp || 0) + '</span>' +
                '<span class="pill">' + esc(s.map || '-') + ' / ' + esc(s.cell || '-') + '</span>' +
                (s.is_dead ? '<span class="pill" style="color:#f87171">dead</span>' : '') +
                (cooldowns ? '<div class="skill-cd" style="display:flex;gap:4px;flex-wrap:wrap;margin-top:6px">' +
                    cooldowns + '</div>' : '');
            if (s.role) {
                var cls = card.querySelector('.slot-class');
                if (cls) cls.textContent = s.role;
            }
        });
    }

    // --- per-player logs ---------------------------------------------------
    // Every line is tagged with the pane's username (each thread registers with
    // the redirector under it), so the page can keep one console per player the
    // way the temple and ultra v1 menus do.  "All" is the merged view.
    var paneUsers = {};              // slot id -> username
    var logBuffers = { all: [] };    // "all" | slot1..slot4 -> [html lines]
    var activeLog = 'all';

    function slotForUser(user) {
        var wanted = String(user || '').trim().toLowerCase();
        if (!wanted) return '';
        for (var i = 0; i < SLOT_IDS.length; i++) {
            if (String(paneUsers[SLOT_IDS[i]] || '').trim().toLowerCase() === wanted) {
                return SLOT_IDS[i];
            }
        }
        return '';
    }

    function buildLogTabs() {
        var bar = document.getElementById('log-tabs');
        if (!bar) return;
        var buttons = ['<button class="console-tab' +
            (activeLog === 'all' ? ' active' : '') + '" data-log="all">All</button>'];
        SLOT_IDS.forEach(function (sId, index) {
            var name = paneUsers[sId] || ('Slot ' + (index + 1));
            if (!logBuffers[sId]) logBuffers[sId] = [];
            buttons.push('<button class="console-tab' +
                (activeLog === sId ? ' active' : '') + '" data-log="' + sId + '">' +
                esc(name) + '</button>');
        });
        bar.innerHTML = buttons.join('');
        Array.prototype.forEach.call(bar.querySelectorAll('[data-log]'),
            function (btn) {
                btn.onclick = function () {
                    activeLog = btn.getAttribute('data-log');
                    buildLogTabs();
                    renderLog();
                };
            });
    }

    function renderLog() {
        var log = document.getElementById('log');
        if (!log) return;
        log.innerHTML = (logBuffers[activeLog] || []).join('');
        var c = document.getElementById('chk-auto-scroll');
        if (!c || c.checked) { log.scrollTop = log.scrollHeight; }
    }

    function appendLog(user, html) {
        var own = slotForUser(user);
        var line = '<div><span class="who">' + esc(user || '') + '</span> ' +
            html + '</div>';
        logBuffers.all.push(line);
        if (own) {
            if (!logBuffers[own]) logBuffers[own] = [];
            logBuffers[own].push(line);
            while (logBuffers[own].length > 800) { logBuffers[own].shift(); }
        }
        while (logBuffers.all.length > 800) { logBuffers.all.shift(); }
        if (activeLog === 'all' || activeLog === own) { renderLog(); }
    }

    window.addUltraLog = function (kind, key, user, html) {
        appendLog(user, html);
    };
    window.addSlaveLog = function (user, html) { appendLog(user, html); };

    // One button: START while idle, STOP while the party runs.  The label is
    // driven by the same status poll the pane cards use, so a party that ends
    // on its own turns the button back to START by itself.
    var partyRunning = false;

    function setButton(running) {
        var btn = document.getElementById('btn-toggle');
        if (!btn) return;
        partyRunning = running;
        btn.textContent = running ? 'STOP' : 'START';
        btn.className = 'btn ' + (running ? 'btn-danger' : 'btn-success');
    }

    function toggleParty() {
        var a = api();
        if (!a) return;
        var btn = document.getElementById('btn-toggle');
        if (btn) btn.disabled = true;
        var done = function () { if (btn) btn.disabled = false; };
        if (partyRunning) {
            a.stop_party().then(function () {
                msg('Stopped.', true);
                setButton(false);
            }).then(done, done);
            return;
        }
        msg('');
        a.start_party(collect()).then(function (res) {
            if (!res || !res.success) {
                msg((res && res.error) || 'Failed to start', false);
                return;
            }
            msg('Party starting...', true);
            setButton(true);
        }).then(done, done);
    }

    window.whenApiReady(function (a) {
        var container = document.getElementById('slots');
        SLOT_IDS.forEach(function (sId, i) { container.appendChild(buildSlot(i, sId)); });

        var ready = a.form ? a.form() : Promise.resolve({});
        ready.then(function (data) {
            form = data || {};
            if (form.title) document.getElementById('title').textContent = form.title;
            fillComposition();
            fillRetries();
            return a.load_config();
        }).then(function (config) {
            applyConfig(config || {});
        });

        document.getElementById('btn-toggle').onclick = toggleParty;
        var clearBtn = document.getElementById('btn-clear-logs');
        if (clearBtn) {
            clearBtn.onclick = function () {
                logBuffers = { all: [] };
                SLOT_IDS.forEach(function (sId) { logBuffers[sId] = []; });
                renderLog();
            };
        }

        // Labels follow whatever is typed in the username boxes, so the tabs
        // read like the temple menu even before a run has started.
        SLOT_IDS.forEach(function (sId) {
            var card = document.querySelector('.slot-card[data-slot="' + sId + '"]');
            var field = card.querySelector('.slot-user');
            field.addEventListener('input', function () {
                paneUsers[sId] = field.value.trim();
                buildLogTabs();
            });
        });

        setInterval(function () {
            a.get_status().then(renderStatus);
        }, 1500);
    });
})();
