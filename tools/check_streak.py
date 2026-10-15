import json, pathlib, sys
from collections import defaultdict

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'i1': 5}
NZ = {1, 2, 3, 4, 5}
def slot(raw):
    try:
        return NAME.get(raw.split('%')[6].split('>')[0], None)
    except Exception:
        return None

def run(path, label):
    recs = [json.loads(l) for l in pathlib.Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]
    gars = [(r['t'], slot(r.get('raw',''))) for r in recs
            if r.get('dir') == 'TX' and r.get('detail') == 'gar']
    warn_t = [r['t'] for r in recs
              if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]

    print('=' * 76)
    print(label)

    # walk the cast sequence tracking streak of consecutive non-zero casts
    streak = 0
    by_pos = defaultdict(lambda: [0, 0])   # streak position -> [casts, warnings]
    max_streak = 0
    for t, s in gars:
        if s is None:
            continue
        if s == 0:
            streak = 0
            continue
        streak += 1
        max_streak = max(max_streak, streak)
        w = any(t <= x < t + 1.2 for x in warn_t)
        by_pos[streak][0] += 1
        by_pos[streak][1] += int(w)

    print('  max consecutive-nonzero streak: %d' % max_streak)
    print('  %-10s %8s %10s %8s' % ('position', 'casts', 'warnings', 'rate'))
    for p in sorted(by_pos):
        c, w = by_pos[p]
        print('  %-10d %8d %10d %7.1f%%' % (p, c, w, 100 * w / max(1, c)))
    print()

run(sys.argv[1], sys.argv[2])
run(sys.argv[3], sys.argv[4])
