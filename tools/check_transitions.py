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
    gars = [(r['t'], slot(r.get('raw',''))) for r in recs
            if r.get('dir') == 'TX' and r.get('detail') == 'gar']
    warn = [r['t'] for r in recs
            if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]

    print('=' * 74)
    print(label)

    def cls(a, b):
        return ('aa' if a == 0 else 'nz') + '->' + ('aa' if b == 0 else 'nz')

    # every transition in the run, bucketed
    bucket_total, bucket_warn = {}, {}
    for (t0, s0), (t1, s1) in zip(gars, gars[1:]):
        if s0 is None or s1 is None:
            continue
        k = cls(s0, s1)
        bucket_total[k] = bucket_total.get(k, 0) + 1

    # a warning "belongs" to the transition that ended closest before it
    for w in warn:
        before = [g for g in gars if g[0] < w]
        if len(before) < 2:
            continue
        gap = (before[-1][0] - before[-2][0]) * 1000
        k = cls(before[-2][1], before[-1][1])
        # only count it if the warning came right after that transition
        if (w - before[-1][0]) < 1.5:
            bucket_warn[k] = bucket_warn.get(k, 0) + 1

    print('  %-10s %8s %10s %8s' % ('transition', 'count', 'warnings', 'rate'))
    for k in sorted(set(bucket_total) | set(bucket_warn)):
        c = bucket_total.get(k, 0)
        w = bucket_warn.get(k, 0)
        print('  %-10s %8d %10d %7.1f%%' % (k, c, w, 100*w/max(1,c)))
    print()

run(sys.argv[1], sys.argv[2])
run(sys.argv[3], sys.argv[4])
