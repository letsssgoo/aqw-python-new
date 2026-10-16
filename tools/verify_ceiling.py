import json, pathlib, statistics

p = pathlib.Path('capture_logs/capture_20261004_195658.jsonl')
recs = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4}
def slot(raw):
    return NAME.get(raw.split('%')[6].split('>')[0], None)

gars = [(r['t'], slot(r.get('raw', ''))) for r in recs
        if r.get('dir') == 'TX' and r.get('detail') == 'gar']

span = max(r['t'] for r in recs if 't' in r) - min(r['t'] for r in recs if 't' in r)

print('Observed same-slot recast cadence (the real achievable period)\n')
print('slot  n   min_gap   p10     p50     theoretical=span/min_gap   actual   deficit')
tot_t = tot_o = 0
for s in range(5):
    times = [t for t, k in gars if k == s]
    gaps = [(b - a) * 1000 for a, b in zip(times, times[1:])]
    if not gaps:
        continue
    mn = min(gaps)
    p10 = sorted(gaps)[max(0, int(len(gaps) * 0.10))]
    theo = int(span / (mn / 1000))
    actual = len(times)
    tot_t += theo
    tot_o += actual
    print('  %d  %4d  %7.0f  %6.0f  %6.0f        %6d        %4d    %+5d'
          % (s, len(gaps), mn, p10, statistics.median(gaps), theo, actual, theo - actual))
print('  TOTAL                                    %6d        %4d    %+5d' % (tot_t, tot_o, tot_t - tot_o))
print()
print('actual %d = %.1f%% of observed-cadence ceiling %d' % (tot_o, 100 * tot_o / tot_t, tot_t))
print()
print('NOTE: min_gap is one sample, so this ceiling is optimistic; p10 is the')
print('      cadence the bot sustained in its best 10%% of recasts.')
print()
print('slot  theo(p10)  actual  deficit')
tt = oo = 0
for s in range(5):
    times = [t for t, k in gars if k == s]
    gaps = sorted((b - a) * 1000 for a, b in zip(times, times[1:]))
    p10 = gaps[max(0, int(len(gaps) * 0.10))]
    theo = int(span / (p10 / 1000))
    tt += theo
    oo += len(times)
    print('  %d    %6d     %4d    %+5d' % (s, theo, len(times), theo - len(times)))
print('  TOTAL %6d     %4d    %+5d  -> actual = %.1f%%' % (tt, oo, tt - oo, 100 * oo / tt))
