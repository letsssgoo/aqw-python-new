import json, pathlib, sys, re

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'i1': 5}
NZ = {1, 2, 3, 4, 5}
def slot(raw):
    try:
        return NAME.get(raw.split('%')[6].split('>')[0], None)
    except Exception:
        return None

def run(path, label):
    recs = [json.loads(l) for l in pathlib.Path(path).read_text(encoding='utf-8').splitlines() if l.strip()]
    gars = [(i, r['t'], slot(r.get('raw',''))) for i, r in enumerate(recs)
            if r.get('dir') == 'TX' and r.get('detail') == 'gar']
    warn_t = [r['t'] for r in recs
              if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]

    print('=' * 76)
    print(label)

    def prev_actref_confirmed(i0, i1, s0):
        """Was there an RX between the two sends carrying actRef for slot s0?"""
        want = 'a0' if s0 == 0 else 'a%d' % s0   # server names slot0 'a0'? see note
        for k in range(i0 + 1, i1):
            r = recs[k]
            if r.get('dir') != 'RX':
                continue
            raw = str(r.get('raw', ''))
            if '"actRef"' in raw:
                refs = re.findall(r'"actRef"\s*:\s*"([^"]+)"', raw)
                if want in refs or 'aa' in refs and s0 == 0:
                    return True
        return False

    stat = {'confirmed': [0, 0], 'unconfirmed': [0, 0]}
    rows = []
    for (i0, t0, s0), (i1, t1, s1) in zip(gars, gars[1:]):
        if s0 not in NZ or s1 not in NZ:
            continue
        ok = prev_actref_confirmed(i0, i1, s0)
        w = any(t1 <= w < t1 + 1.2 for w in warn_t)
        key = 'confirmed' if ok else 'unconfirmed'
        stat[key][0] += 1
        stat[key][1] += int(w)
        rows.append((s0, s1, round((t1 - t0) * 1000), ok, w))

    for k in ('confirmed', 'unconfirmed'):
        c, w = stat[k]
        print('  prev cast actRef %-11s: %3d transitions, %2d warned (%.1f%%)'
              % (k, c, w, 100 * w / max(1, c)))
    print('  warned rows:')
    for r in rows:
        if r[4]:
            print('    ', r)
    print()


run(sys.argv[1], sys.argv[2])
run(sys.argv[3], sys.argv[4])
