#!/bin/bash
# DeepSeek 积分评分 — 双周自动运行
cd /Users/allen/wechat-group-stats

# Read API keys from Hermes env
export DEEPSEEK_API_KEY=$(grep DEEPSEEK_API_KEY ~/.hermes/.env | cut -d= -f2)

# Run scoring (14 days, sample 15 per user)
python3 -c "
import json, uuid, psycopg2, urllib.request, sys, os
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
import importlib.util

BASE_DIR = Path('/Users/allen/wechat-group-stats')
sys.path.insert(0, str(BASE_DIR))
spec = importlib.util.spec_from_file_location('ws', str(BASE_DIR / 'wechat-stats.py'))
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)

api_key = os.environ.get('DEEPSEEK_API_KEY','').strip()
if not api_key:
    print('ERROR: DEEPSEEK_API_KEY not set')
    sys.exit(1)

with open('/tmp/supabase_pass.bin','rb') as f: db_pwd = f.read().decode()
since_ts = int((datetime.now()-timedelta(days=14)).timestamp())
mdbs = sorted([str(p) for p in (Path.home()/'wechat-decrypt'/'decrypted'/'message').glob('message_*.db') if p.name.startswith('message_') and not p.name.endswith('_fts.db')])
cdb = str(Path.home()/'wechat-decrypt'/'decrypted'/'contact'/'contact.db')

msgs = ws.extract_messages_for_push(cdb, mdbs, '45379818937@chatroom', since_ts)
by_s = defaultdict(list)
for m in msgs: by_s[m['sender_id']].append(m)

_, cbw = ws.build_contact_map(cdb)
raw = ws.resolve_sender_wxid(cdb, mdbs, '45379818937@chatroom', list(by_s.keys()))
names = {}
for sid in by_s:
    v = raw.get(sid)
    w = v[0] if isinstance(v, tuple) else v
    names[sid] = cbw.get(w,str(w)) if w else f'u{sid}'

P = '评估群成员发言。0-10分。active/sharer/researcher/collaborator。JSON: {\"active\":N,\"sharer\":N,\"researcher\":N,\"collaborator\":N,\"summary\":\"...\",\"dragon_ball_nominee\":bool}\\n消息:\\n'
scores = {}
for i,(sid,ms) in enumerate(sorted(by_s.items(), key=lambda x:-len(x[1]))):
    nm = names.get(sid,f'u{sid}')
    smp = sorted(ms, key=lambda m:-len(m['content']))[:15]
    txt = '\\n'.join([f'[{datetime.fromtimestamp(m[\"sent_at\"]).strftime(\"%m-%d %H:%M\")}] {m[\"content\"][:200]}' for m in smp])
    pld = json.dumps({'model':'deepseek-chat','messages':[{'role':'system','content':'只输出JSON。'},{'role':'user','content':P+txt}],'temperature':0.3,'max_tokens':300}).encode()
    req = urllib.request.Request('https://api.deepseek.com/v1/chat/completions',data=pld,headers={'Content-Type':'application/json','Authorization':f'Bearer {api_key}'})
    try:
        r = urllib.request.urlopen(req,timeout=60)
        sc = json.loads(json.loads(r.read())['choices'][0]['message']['content'])
        scores[sid]=sc
    except:
        scores[sid]={'active':0,'sharer':0,'researcher':0,'collaborator':0,'summary':'','dragon_ball_nominee':False}
    if (i+1)%10==0: import time; time.sleep(2)

# Push to Supabase
conn = psycopg2.connect(host='13.200.110.68',port=6543,user='postgres.zycgwpaqmjwmliyhcwiv',password=db_pwd,dbname='postgres',connect_timeout=10)
cur=conn.cursor()
cur.execute(\"SELECT id FROM cycles WHERE status='active' LIMIT 1\")
cid=cur.fetchone()[0]
now=datetime.now()
for sid,sc in scores.items():
    nm=names.get(sid,f'u{sid}')
    cur.execute('SELECT id FROM users WHERE username=%s',(nm,))
    row=cur.fetchone()
    uid=row[0] if row else None
    if not uid:
        uid=str(uuid.uuid4())
        cur.execute('INSERT INTO users (id,username,\"inviteCode\",\"createdAt\",\"updatedAt\") VALUES (%s,%s,%s,%s,%s)',(uid,nm,f'a-{uuid.uuid4().hex[:8]}',now,now))
    cur.execute('''INSERT INTO scores (id,\"userId\",\"cycleId\",\"activePoints\",\"sharerPoints\",\"researcherPoints\",\"collaboratorPoints\",\"dragonBalls\")
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT (\"userId\",\"cycleId\") DO UPDATE SET
        \"activePoints\"=EXCLUDED.\"activePoints\",\"sharerPoints\"=EXCLUDED.\"sharerPoints\",\"researcherPoints\"=EXCLUDED.\"researcherPoints\",\"collaboratorPoints\"=EXCLUDED.\"collaboratorPoints\",\"dragonBalls\"=EXCLUDED.\"dragonBalls\"
    ''',(str(uuid.uuid4()),uid,cid,sc.get('active',0),sc.get('sharer',0),sc.get('researcher',0),sc.get('collaborator',0),1 if sc.get('dragon_ball_nominee') else 0))
conn.commit()
conn.close()
print(f'Done: {len(scores)} scores')
" 2>&1
