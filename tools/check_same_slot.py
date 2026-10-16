import json, pathlib, sys
from collections import Counter

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'i1': 5}

def load(path):
    p = pathlib.Path(path)
    return [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

def slot(raw):
    try:
        return NAME.get(raw.split('%')[6].split('>')[0], None)
    except Exception:
        return None

for path, label in ((sys.argv[1], sys.argv[2]), (sys.argv[3], sys.argv[4])):
    recs = load(path)
    gars = [(r['t'], slot(r.get('raw',''))) for r in recs
            if r.get('dir') == 'TX' and r.get('detail') == 'gar']
    warn = [r['t'] for r in recs
            if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]

    print('=' * 72)
    print(label)

    # same-slot recast gaps
    print('  same-slot recast gap ms by slot (p50 / min):')
    for s in range(5):
        t = [x for x, k in gars if k == s]
        gaps = [(b - a) * 1000 for a, b in zip(t, t[1:])]
        if gaps:
            gaps.sort()
            print('     slot %d: n=%3d  min=%5.0f  p50=%5.0f  p10=%5.0f'
                  % (s, len(gaps), gaps[0], gaps[len(gaps)//2], gaps[len(gaps)//10]))

    # for each warning: was the LAST cast an early same-slot recast?
    print('  per warning - last cast slot and time since its previous same-slot cast:')
    slot_mins = {}
    for s in range(5):
        t = [x for x, k in gars if k == s]
        g = sorted((b - a) * 1000 for a, b in zip(t, t[1:]))
        if g:
            slot_mins[s] = g[0]
    hits = 0
    for w in warn:
        before = [g for g in gars if g[0] < w]
        if not before:
            continue
        t, s = before[-1]
        prev = [g for g in before if g[1] == s and g[0] < t]
        since = (t - prev[-1][0]) * 1000 if prev else None
        mn = slot_mins.get(s)
        flag = ''
        if since is not None and mn is not None:
            flag = '  (slot min gap = %.0f)' % mn
            if since <= mn + 1:
                hits += 1
        print('     last=slot%s since_prev_same=%s%s'
              % (s, ('%.0f ms' % since) if since is not None else 'n/a(first)', flag))
    print('  warnings where the last cast equalled the slot minimum: %d/%d'
          % (hits, len(warn)))
    print()
