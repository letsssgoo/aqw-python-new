import json, pathlib, statistics, sys
from collections import Counter

p = pathlib.Path(sys.argv[1])
recs = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

NAME = {'aa': 0, 'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'i1': 5}
def slot(raw):
    try:
        return NAME.get(raw.split('%')[6].split('>')[0], None)
    except Exception:
        return None

ts = [r['t'] for r in recs if 't' in r]
span = max(ts) - min(ts)
print('span %.1fs  records %d' % (span, len(recs)))

uses = [r for r in recs if r.get('kind') == 'use_skill']
ok = [r for r in uses if r['detail'] == 'ok']
skip = [r for r in uses if r['detail'] == 'skipped']
print('use_skill  ok=%d  skipped=%d  efficiency=%.1f%%'
      % (len(ok), len(skip), 100 * len(ok) / max(1, len(uses))))

nxt = [r for r in recs if r.get('kind') == 'use_next_skill']
print('use_next_skill  cast=%d  idle=%d'
      % (sum(1 for r in nxt if r['detail'] == 'cast'),
         sum(1 for r in nxt if r['detail'] == 'idle')))
idle_wait = [r['waited_ms'] for r in nxt if r['detail'] == 'idle' and r.get('waited_ms')]
if idle_wait:
    print('   idle wait ms: p50=%.0f max=%.0f' % (statistics.median(idle_wait), max(idle_wait)))

warn = [r for r in recs if r.get('kind') == 'xt' and 'slow down' in str(r.get('raw','')).lower()]
deaths = [r for r in recs if r.get('detail') == 'playerDeath']
backoff = [r for r in recs if 'backoff' in str(r)]
print('warnings=%d  deaths=%d' % (len(warn), len(deaths)))

gars = [(r['t'], slot(r.get('raw',''))) for r in recs
        if r.get('dir') == 'TX' and r.get('detail') == 'gar']
print('gar packets=%d  rate=%.2f/s' % (len(gars), len(gars)/span))
gaps = [(b[0]-a[0])*1000 for a, b in zip(gars, gars[1:])]
if gaps:
    print('gar gap ms: min=%.0f p50=%.0f p10=%.0f  <300:%d  <400:%d'
          % (min(gaps), statistics.median(gaps), sorted(gaps)[len(gaps)//10],
             sum(1 for g in gaps if g < 300), sum(1 for g in gaps if g < 400)))

print('\nWARNINGS vs preceding gar gap:')
for w in warn[:12]:
    prev = [g for g in gars if g[0] < w['t']]
    if len(prev) >= 2:
        print('  %s  last_two_gap=%5.0f ms  last_slot=%s  to_warning=%4.0f ms'
              % (w['ts'], (prev[-1][0]-prev[-2][0])*1000, prev[-1][1],
                 (w['t']-prev[-1][0])*1000))

print('\ncasts by slot:', dict(Counter(s for _, s in gars if s is not None)))
print('elapsed_ms of ok casts: mean=%.0f' % statistics.mean(
    [r['elapsed_ms'] for r in ok if r.get('elapsed_ms') is not None]))

# spam backoff events
print('\nbackoff prints / lifecycle:')
for r in recs:
    if r.get('kind') in ('lifecycle',) or 'backoff' in str(r.get('detail','')):
        print('  ', r['ts'], r.get('kind'), r.get('detail'))
