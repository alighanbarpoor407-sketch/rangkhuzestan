import os
import json
import secrets
import hashlib
import base64
import getpass
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

BASE = os.path.dirname(os.path.abspath(__file__))
ORDERS_FILE = os.path.join(BASE, "orders.json")
AUTH_FILE = os.path.join(BASE, "admin_auth.json")
sessions = set()

def make_hash(password):
    salt = secrets.token_bytes(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
    return base64.b64encode(salt).decode(), base64.b64encode(h).decode()

def check_password(password):
    with open(AUTH_FILE, encoding="utf-8") as f:
        a = json.load(f)
    salt = base64.b64decode(a["salt"])
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200000)
    return secrets.compare_digest(base64.b64encode(h).decode(), a["hash"])

print("ADMIN_PASSWORD:", "SET" if os.environ.get("ADMIN_PASSWORD") else "NOT_SET")

if not os.path.exists(AUTH_FILE):
    env_password = os.environ.get("ADMIN_PASSWORD")
    if not env_password:
        raise RuntimeError("ADMIN_PASSWORD is not set")
    if len(env_password) < 6:
        raise ValueError("ADMIN_PASSWORD must be at least 6 characters")

    salt, h = make_hash(env_password)

    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump({"salt": salt, "hash": h}, f)

    print("رمز مدیریت از Environment Variable ساخته شد.")


def orders():
    try:
        with open(ORDERS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save(data):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

LOGIN = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ورود مدیریت</title>
<style>
body{font-family:Tahoma;background:#f1f4f7}
.box{max-width:380px;margin:80px auto;background:white;padding:25px;border-radius:16px;box-shadow:0 3px 15px #0002}
input,button{width:100%;box-sizing:border-box;padding:14px;margin-top:15px;border-radius:9px;font-family:inherit}
input{border:1px solid #ddd}
button{border:0;background:#1565c0;color:white}
h2{text-align:center}
</style>
</head>
<body>
<div class="box">
<h2>🔐 پنل مدیریت</h2>
<form method="post" action="/api/login">
<input name="password" type="password" placeholder="رمز مدیریت" required autofocus>
<button>ورود</button>
</form>
</div>
</body>
</html>"""

ADMIN = """<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>مدیریت سفارش‌ها</title>
<style>
body{margin:0;font-family:Tahoma;background:#f4f6f8;color:#222}
header{background:#123f75;color:white;padding:20px;text-align:center}
main{max-width:900px;margin:20px auto;padding:10px}
.order{background:white;border-radius:15px;padding:18px;margin-bottom:18px;box-shadow:0 2px 10px #0002}
.info{line-height:2;background:#f8f9fa;padding:12px;border-radius:10px}
label{display:block;font-weight:bold;margin-top:12px}
input,select,textarea{width:100%;box-sizing:border-box;padding:11px;margin-top:6px;border:1px solid #ddd;border-radius:8px;font-family:inherit}
textarea{min-height:70px}
button{border:0;border-radius:8px;padding:11px 16px;margin-top:15px;background:#1565c0;color:white;font-family:inherit}
.logout{background:#777}
</style>
</head>
<body>
<header><h2>🎨 رنگ خوزستان</h2><p>پنل مدیریت سفارش‌ها</p></header>
<main>
<button class="logout" onclick="logout()">خروج</button>
<div id="orders">در حال دریافت...</div>
</main>
<script>
function e(v){
return String(v??'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
async function load(){
const r=await fetch('/api/orders');
if(r.status===401){location='/admin';return}
const a=await r.json();
const box=document.getElementById('orders');
if(!a.length){box.innerHTML='<div class="order"><h3>هنوز سفارشی ثبت نشده است.</h3></div>';return}
box.innerHTML=a.map(o=>`
<div class="order">
<h3>📦 سفارش ${e(o.id)}</h3>
<div class="info">
<b>زمان:</b> ${e(o.time)}<br>
<b>نام:</b> ${e(o.name)}<br>
<b>تلفن:</b> ${e(o.phone)}<br>
<b>شهر:</b> ${e(o.city)}<br>
<b>محصول:</b> ${e(o.product)}<br>
<b>مقدار:</b> ${e(o.quantity)}<br>
<b>برند:</b> ${e(o.brand||'ندارد')}<br>
<b>دریافت:</b> ${e(o.delivery)}<br>
<b>آدرس:</b> ${e(o.address||'---')}<br>
<b>توضیحات:</b> ${e(o.description||'---')}
</div>
<label>وضعیت</label>
<select id="s${o.id}">
<option ${o.status==='جدید'?'selected':''}>جدید</option>
<option ${o.status==='در حال بررسی'?'selected':''}>در حال بررسی</option>
<option ${o.status==='قیمت اعلام شد'?'selected':''}>قیمت اعلام شد</option>
<option ${o.status==='تأیید مشتری'?'selected':''}>تأیید مشتری</option>
<option ${o.status==='تهیه شد'?'selected':''}>تهیه شد</option>
<option ${o.status==='تحویل شد'?'selected':''}>تحویل شد</option>
</select>
<label>هزینه تهیه</label>
<input id="c${o.id}" value="${e(o.procurement_cost)}">
<label>هزینه ارسال</label>
<input id="sh${o.id}" value="${e(o.shipping_cost)}">
<label>قیمت نهایی</label>
<input id="p${o.id}" value="${e(o.final_price)}">
<label>یادداشت</label>
<textarea id="n${o.id}">${e(o.note)}</textarea>
<button onclick="saveOrder('${o.id}')">💾 ذخیره</button>
</div>`).join('');
}
async function saveOrder(id){
const data={
status:document.getElementById('s'+id).value,
procurement_cost:document.getElementById('c'+id).value,
shipping_cost:document.getElementById('sh'+id).value,
final_price:document.getElementById('p'+id).value,
note:document.getElementById('n'+id).value
};
const r=await fetch('/api/order/'+id,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
if(r.ok){alert('ذخیره شد');load()}else{alert('خطا')}
}
async function logout(){await fetch('/api/logout',{method:'POST'});location='/admin'}
load();
</script>
</body>
</html>"""

class Handler(BaseHTTPRequestHandler):

    def send(self, code, data, typ="text/html; charset=utf-8"):
        if isinstance(data,str):
            data=data.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type",typ)
        self.send_header("Content-Length",str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def auth(self):
        c=self.headers.get("Cookie","")
        for x in c.split(";"):
            if x.strip().startswith("session="):
                return x.strip().split("=",1)[1] in sessions
        return False

    def do_HEAD(self):
        self.do_GET()
    def do_GET(self):
        p=urlparse(self.path).path

        if p=="/":
            with open(os.path.join(BASE,"index.html"),encoding="utf-8") as f:
                self.send(200,f.read())
            return

        if p=="/robots.txt":
            with open(os.path.join(BASE,"robots.txt"),encoding="utf-8") as f:
                self.send(200,f.read(),"text/plain; charset=utf-8")
            return

        if p=="/sitemap.xml":
            with open(os.path.join(BASE,"sitemap.xml"),encoding="utf-8") as f:
                self.send(200,f.read(),"application/xml; charset=utf-8")
            return

        if p=="/admin":
            self.send(200,ADMIN if self.auth() else LOGIN)
            return

        if p=="/api/orders":
            if not self.auth():
                self.send(401,"Unauthorized")
                return
            self.send(200,json.dumps(orders(),ensure_ascii=False),"application/json")
            return

        self.send(404,"Not Found")

    def do_POST(self):
        p=urlparse(self.path).path
        n=int(self.headers.get("Content-Length","0"))
        raw=self.rfile.read(n)

        if p=="/api/login":
            form=parse_qs(raw.decode())
            password=form.get("password",[""])[0]
            if check_password(password):
                token=secrets.token_urlsafe(32)
                sessions.add(token)
                self.send_response(303)
                self.send_header("Location","/admin")
                self.send_header("Set-Cookie",f"session={token}; HttpOnly; SameSite=Strict; Path=/")
                self.end_headers()
            else:
                self.send(401,b"Wrong password")
            return

        if p=="/api/logout":
            c=self.headers.get("Cookie","")
            for x in c.split(";"):
                if x.strip().startswith("session="):
                    sessions.discard(x.strip().split("=",1)[1])
            self.send(200,"OK")
            return

        if p=="/api/orders":
            try:
                o=json.loads(raw.decode())
                a=orders()
                o["id"]=str(len(a)+1).zfill(4)
                o["status"]="جدید"
                o["procurement_cost"]=""
                o["shipping_cost"]=""
                o["final_price"]=""
                o["note"]=""
                a.insert(0,o)
                save(a)
                self.send(200,json.dumps({"ok":True,"id":o["id"]}),"application/json")
            except Exception as ex:
                self.send(400,json.dumps({"ok":False,"error":str(ex)}),"application/json")
            return

        if p.startswith("/api/order/"):
            if not self.auth():
                self.send(401,"Unauthorized")
                return
            oid=p.split("/")[-1]
            try:
                changes=json.loads(raw.decode())
                a=orders()
                found=False
                for o in a:
                    if o.get("id")==oid:
                        o.update(changes)
                        found=True
                        break
                if found:
                    save(a)
                    self.send(200,'{"ok":true}',"application/json")
                else:
                    self.send(404,'{"ok":false}',"application/json")
            except Exception as ex:
                self.send(400,json.dumps({"error":str(ex)}),"application/json")
            return

        self.send(404,"Not Found")

print("================================")
print("رنگ خوزستان - سرور آماده است")
print("سایت:   http://0.0.0.0:8080")
print("مدیریت: http://0.0.0.0:8080/admin")
print("================================")

server=ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", 8080))),Handler)

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("سرور متوقف شد")
    server.server_close()
