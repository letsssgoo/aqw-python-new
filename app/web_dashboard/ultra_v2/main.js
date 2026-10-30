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
        sel.innerHTML = (spec.choices || []).map(function (c) {
            return '<option value="' + esc(c.value) + '">' + esc(c.label) + ' \u2014 ' +
                esc(c.help || '') + '</option>';
        }).join('');
        // The tooltip text the backend uses for the whole table, so the dropdown
        // and the run's own log line can never disagree.
        var hint = document.getElementById('composition-hint');
        if (hint) {
            hint.innerHTML = (spec.help || '').split('\n')
                .map(esc).join('<br>');
        }
        sel.onchange = refreshPreview;
    }

    function refreshPreview() {
        var sel = document.getElementById('composition');
        if (!api() || !api().summary) return;
        api().summary().then(function (data) {
            var box = document.getElementById('composition-preview');
            if (!box || !data) return;
            var rows = (data.slots || []).map(function (s) {
                return '<span class="pill">slot ' + s.slot + ': ' + esc(s.cls) + '</span>';
            }).join(' ');
            box.innerHTML = 'This composition wears: ' + rows;
        });
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
        document.getElementById('private-room').value = config.private_room || 0;
        if (config.retries) document.getElementById('retries').value = String(config.retries);
        document.getElementById('use-potions').checked = config.use_potions !== false;
        document.getElementById('use-enhancements').checked = config.use_enhancements !== false;
        var slots = config.slots || {};
        SLOT_IDS.forEach(function (sId) {
            var card = document.querySelector('.slot-card[data-slot="' + sId + '"]');
            var s = slots[sId] || {};
            if (s.username) card.querySelector('.slot-user').value = s.username;
            if (s.password) card.querySelector('.slot-pass').value = s.password;
        });
        refreshPreview();
    }

    function collect() {
        var config = {
            server: document.getElementById('server').value || 'Alteon',
            room_number: parseInt(document.getElementById('room').value || '9099', 10),
            composition: document.getElementById('composition').value,
            private_room: parseInt(document.getElementById('private-room').value || '0', 10),
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
            el.innerHTML =
                '<span class="pill">' + esc(s.username || '-') + '</span>' +
                '<span class="pill">HP ' + hp + '%</span>' +
                '<span class="pill">MP ' + (s.mp || 0) + '</span>' +
                '<span class="pill">' + esc(s.map || '-') + ' / ' + esc(s.cell || '-') + '</span>' +
                (s.is_dead ? '<span class="pill" style="color:#f87171">dead</span>' : '');
            if (s.role) {
                var cls = card.querySelector('.slot-class');
                if (cls) cls.textContent = s.role;
            }
        });
    }

    window.addUltraLog = function (kind, key, user, html) {
        var log = document.getElementById('log');
        if (!log) return;
        var line = document.createElement('div');
        line.innerHTML = '<span class="who">' + esc(user || '') + '</span> ' + html;
        log.appendChild(line);
        while (log.childNodes.length > 500) { log.removeChild(log.firstChild); }
        var c = document.getElementById('chk-auto-scroll');
        if (!c || c.checked) { log.scrollTop = log.scrollHeight; }
    };
    window.addSlaveLog = function (user, html) { window.addUltraLog('', '', user, html); };

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
            // The saved values win over the schema defaults; only then does the
            // preview know which composition is really selected.
            refreshPreview();
        });

        document.getElementById('btn-start').onclick = function () {
            msg('');
            a.start_party(collect()).then(function (res) {
                if (!res || !res.success) { msg((res && res.error) || 'Failed to start', false); return; }
                msg('Party starting...', true);
            });
        };
        document.getElementById('btn-stop').onclick = function () {
            a.stop_party().then(function () { msg('Stopped.', true); });
        };
        var clearBtn = document.getElementById('btn-clear-logs');
        if (clearBtn) { clearBtn.onclick = function () { document.getElementById('log').innerHTML = ''; }; }

        setInterval(function () { a.get_status().then(renderStatus); }, 1500);
    });
})();
