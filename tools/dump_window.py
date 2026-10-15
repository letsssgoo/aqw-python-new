import json, pathlib, sys

p = pathlib.Path(sys.argv[1])
target = sys.argv[2]  # HH:MM:SS.mmm
recs = [json.loads(l) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]

idx = next((i for i, r in enumerate(recs) if r.get('ts', '').startswith(target)), None)
if idx is None:
    print('not found'); raise SystemExit

print('--- window around %s ---' % target)
for r in recs[max(0, idx - 14):idx + 3]:
    d = r.get('dir')
    if d == 'TX':
        print('  TX %-16s %s' % (r.get('detail'), str(r.get('raw',''))[:66]))
    elif d == 'RX':
        raw = str(r.get('raw',''))
        show = raw if len(raw) < 90 else raw[:88] + '...'
        print('      RX %-14s %s' % (r.get('detail'), show))
    else:
        extra = {k: v for k, v in r.items()
                 if k not in ('t','ts','dir','kind','detail','raw')}
        print('  EVT %-14s %-8s %s' % (r.get('kind'), r.get('detail'), extra))
