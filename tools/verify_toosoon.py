import json, pathlib

p = pathlib.Path('capture_logs/capture_20261004_195658.jsonl')
recs = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4}

def slot(raw):
    # %xt%zm%gar%1%0%a2>m:22%wvz%
    tgt = raw.split('%')[6]
    key = tgt.split('>')[0]
    return NAME.get(key, key)

gars = [(r['t'], slot(r.get('raw', '')), r.get('raw', '')) for r in recs
        if r.get('dir') == 'TX' and r.get('detail') == 'gar']

warn = [r['t'] for r in recs
        if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw', '')).lower()]

CDR = 0.2258
cd = {0: 1500, 1: 6000, 2: 6000, 3: 6000, 4: 12000}
eff = {k: v * (1 - CDR) for k, v in cd.items()}

print('For each warning, which action was "too soon"?\n')
for w in warn:
    before = [g for g in gars if g[0] < w]
    print('WARNING at t=%.3f' % w)
    for t, s, raw in before[-3:]:
        prev_same = [g for g in before if g[1] == s and g[0] < t]
        since = (t - prev_same[-1][0]) * 1000 if prev_same else float('inf')
        print('   gar slot=%-2s t=%.3f  since_previous_same_slot=%7.0f ms  eff_cd=%.0f ms  %s'
              % (s, t, since, eff.get(s, -1),
                 '<-- TOO SOON' if since < eff.get(s, 0) else ''))
    print()

# Across the whole run: how often did we send a skill EARLIER than its effective cd?
too_soon = 0
total = 0
worst = []
for (t, s, raw), (t2, s2, _) in zip(gars, gars[1:]):
    if s != s2:
        continue
for t, s, raw in gars:
    if s not in eff:
        continue
    prev = [g for g in gars if g[1] == s and g[0] < t]
    if not prev:
        continue
    total += 1
    since = (t - prev[-1][0]) * 1000
    if since < eff[s]:
        too_soon += 1
        worst.append((eff[s] - since, s, since))

print('same-slot recast timing over the run:')
print('   same-slot recasts measured: %d' % total)
print('   sent BEFORE effective cd:   %d (%.1f%%)' % (too_soon, 100 * too_soon / total))
if worst:
    worst.sort(reverse=True)
    print('   worst undershoots (ms early, slot, actual gap):',
          [(round(a), b, round(c)) for a, b, c in worst[:8]])
