import json, pathlib, statistics
from collections import Counter, defaultdict

p = pathlib.Path('capture_logs/capture_20261004_195658.jsonl')
recs = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

CDR = 0.2258
cd = {0: 1500, 1: 6000, 2: 6000, 3: 6000, 4: 12000}

# --- slot 0 block reasons ---
b0 = [r for r in recs if r.get('kind') == 'canUseSkill' and r['detail'] == 'blocked' and r.get('skill') == 0]
print('slot0 blocks:', len(b0), 'reasons:', dict(Counter(r.get('reason') for r in b0)))

# --- per-slot: time since last successful cast at each block ---
oks = defaultdict(list)
for r in recs:
    if r.get('kind') == 'use_skill' and r['detail'] == 'ok':
        oks[r['skill']].append(r['t'])

print()
print('slot  n_blk  eff_cd   min_since  p50_since  max_since  blocks_late(>eff+200ms)')
for s in sorted(cd):
    eff = cd[s] * (1 - CDR)
    gaps = []
    for r in recs:
        if r.get('kind') == 'canUseSkill' and r['detail'] == 'blocked' and r.get('skill') == s:
            prev = [t for t in oks[s] if t < r['t']]
            if prev:
                gaps.append((r['t'] - prev[-1]) * 1000)
    if not gaps:
        continue
    late = [x for x in gaps if x > eff + 200]
    print(f'  {s}   {len(gaps):4}   {eff:6.0f}   {min(gaps):8.0f}   {statistics.median(gaps):8.0f}   {max(gaps):8.0f}      {len(late):4} ({100*len(late)/len(gaps):.1f}%)')

# --- why slot 0 blocks: gap between its two visits vs its cd ---
casts = sorted([(r['t'], r['skill']) for r in recs if r.get('kind') == 'use_skill' and r['detail'] == 'ok'])
g00 = [(t1 - t0) * 1000 for (t0, s0), (t1, s1) in zip(casts, casts[1:]) if s0 == 0 and s1 == 0]
print()
print('0->0 successful gap: n=%d min=%.0f p50=%.0f mean=%.0f  (eff cd=%.0fms)' % (
    len(g00), min(g00), statistics.median(g00), statistics.mean(g00), cd[0] * (1 - CDR)))

# --- attempt/cast by rotation position ---
print()
print('rotation [0,1,2,0,3,4] -> slot0 appears at positions 0 and 3')
att = Counter(r['skill'] for r in recs if r.get('kind') == 'use_skill')
okc = Counter(r['skill'] for r in recs if r.get('kind') == 'use_skill' and r['detail'] == 'ok')
print('slot0 attempts', att[0], 'ok', okc[0], 'blocked', att[0] - okc[0])

# --- gate cost ---
g = defaultdict(list)
for (t0, s0), (t1, s1) in zip(casts, casts[1:]):
    if s0 == 0 and s1 != 0:
        g['0->nz'].append((t1 - t0) * 1000)
    elif s0 != 0 and s1 == 0:
        g['nz->0'].append((t1 - t0) * 1000)
a, b = statistics.median(g['0->nz']), statistics.median(g['nz->0'])
print()
print('gate cost per 0->nz: %.0f - %.0f = %.0fms  x%d = %.0fs' % (a, b, a - b, len(g['0->nz']), (a - b) * len(g['0->nz']) / 1000))
