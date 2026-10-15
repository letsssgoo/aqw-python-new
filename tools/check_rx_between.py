import json, pathlib, sys

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'i1': 5}
NZ = {1, 2, 3, 4, 5}
def slot(raw):
    try:
        return NAME.get(raw.split('%')[6].split('>')[0], None)
    except Exception:
        return None

def run(path, label):
    recs = [json.loads(l) for l in pathlib.Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]
    events = sorted([r for r in recs if 't' in r], key=lambda r: r['t'])
    gars = [(i, r['t'], slot(r.get('raw',''))) for i, r in enumerate(recs)
            if r.get('dir') == 'TX' and r.get('detail') == 'gar']
    warn_t = [r['t'] for r in recs
              if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]

    print('=' * 76)
    print(label)

    stats = {'with_rx': [0, 0], 'without_rx': [0, 0]}   # [count, warnings]
    detail = []
    for (i0, t0, s0), (i1, t1, s1) in zip(gars, gars[1:]):
        if s0 not in NZ or s1 not in NZ:
            continue
        # any RX record strictly between the two sends?
        rx_between = any(recs[k].get('dir') == 'RX' for k in range(i0 + 1, i1))
        w = any(t1 <= w < t1 + 1.2 for w in warn_t)
        key = 'with_rx' if rx_between else 'without_rx'
        stats[key][0] += 1
        stats[key][1] += int(w)
        detail.append((s0, s1, (t1 - t0) * 1000, rx_between, w))

    for k in ('with_rx', 'without_rx'):
        c, w = stats[k]
        print('  nz->nz with RX in between: %4d transitions, %3d warned (%.1f%%)'
              % (c, w, 100 * w / max(1, c)) if k == 'with_rx' else
              '  nz->nz with NO RX in between: %4d transitions, %3d warned (%.1f%%)'
              % (c, w, 100 * w / max(1, c)))

    print('  first 12 nz->nz: (prev,next,gap_ms,RX?,warned?)')
    for d in detail[:12]:
        print('     %s' % (d,))
    if len(detail) > 12:
        print('     ... %d more' % (len(detail) - 12))
        print('     warned ones:')
        for d in detail:
            if d[4]:
                print('       %s' % (d,))
    print()

run(sys.argv[1], sys.argv[2])
run(sys.argv[3], sys.argv[4])
