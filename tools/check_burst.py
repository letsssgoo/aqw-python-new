import json, pathlib, sys
from collections import Counter

def analyse(path, label):
    p = pathlib.Path(path)
    recs = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
    gars = [r['t'] for r in recs if r.get('dir') == 'TX' and r.get('detail') == 'gar']
    warn = [r['t'] for r in recs
            if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]
    span = max(r['t'] for r in recs if 't' in r) - min(r['t'] for r in recs if 't' in r)

    print('=' * 70)
    print('%s   span=%.0fs  casts=%d  warnings=%d  (%.2f%% of casts)'
          % (label, span, len(gars), len(warn), 100*len(warn)/max(1,len(gars))))

    # how many casts happened in the 1.5s BEFORE each warning?
    print('\n  casts in the 1.5s window before each warning:')
    pre = []
    for w in warn:
        n = sum(1 for g in gars if 0 <= (w - g) < 1.5)
        pre.append(n)
        print('     %d casts' % n)
    if pre:
        print('     -> mean %.1f' % (sum(pre)/len(pre)))

    # distribution of casts-per-1.5s across the WHOLE run, sampled at every cast
    allwin = [sum(1 for g in gars if 0 <= (t - g) < 1.5) for t in gars]
    hist = Counter(allwin)
    print('  casts-in-1.5s histogram over all casts: %s'
          % dict(sorted(hist.items())))

    # warnings per bucket of local rate
    print('  warning rate by local cast density:')
    buckets = {}
    for t in gars:
        n = sum(1 for g in gars if 0 <= (t - g) < 1.5)
        w = sum(1 for x in warn if 0 <= (x - t) < 0.6)
        b = min(n, 6)
        buckets.setdefault(b, [0, 0])
        buckets[b][0] += 1
        buckets[b][1] += w
    for b in sorted(buckets):
        c, w = buckets[b]
        print('     density %d: %4d casts, %3d warnings nearby (%.1f%%)'
              % (b, c, w, 100*w/c))
    print()


analyse(sys.argv[1], sys.argv[2])
analyse(sys.argv[3], sys.argv[4])
