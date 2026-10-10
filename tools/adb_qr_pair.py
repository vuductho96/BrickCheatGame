"""ADB QR pairing session using the same payload as Android Studio."""
import json
import secrets
import string
import subprocess
import time
from pathlib import Path
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
ADB=ROOT/"tools"/"platform-tools"/"adb.exe"
ARTIFACTS=ROOT/"artifacts"
ARTIFACTS.mkdir(exist_ok=True)
SESSION=ARTIFACTS/"adb-qr-session.json"
STATUS=ARTIFACTS/"adb-qr-status.json"

def adb(*args,timeout=5):
    result=subprocess.run([str(ADB),*args],capture_output=True,timeout=timeout,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    return result.returncode,result.stdout.decode("utf8","replace").strip(),result.stderr.decode("utf8","replace").strip()

def status(phase,**fields):
    STATUS.write_text(json.dumps({"phase":phase,**fields},ensure_ascii=False,indent=2),encoding="utf8")

def create():
    identity="studio-"+''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(10))
    password=''.join(secrets.choice(string.digits) for _ in range(10))
    payload=f"WIFI:T:ADB;S:{identity};P:{password};;"
    matrix=cv2.QRCodeEncoder_create().encode(payload)
    matrix=cv2.copyMakeBorder(matrix,4,4,4,4,cv2.BORDER_CONSTANT,value=255)
    image=cv2.resize(matrix,(600,600),interpolation=cv2.INTER_NEAREST)
    decoded,_,_=cv2.QRCodeDetector().detectAndDecode(image)
    if decoded!=payload:
        raise RuntimeError("QR round-trip verification failed")
    cv2.imwrite(str(ARTIFACTS/"adb-pairing-qr.png"),image)
    SESSION.write_text(json.dumps({"identity":identity,"password":password,"expires":time.time()+900}),encoding="utf8")
    status("waiting_for_scan",expires_in_seconds=900)
    print("QR created and decode verified.")

def listen():
    session=json.loads(SESSION.read_text(encoding="utf8"))
    identity,password=session["identity"],session["password"]
    status("waiting_for_scan",expires_in_seconds=max(0,int(session["expires"]-time.time())))
    last_attempt=0
    paired_ip=None
    while time.time()<session["expires"]:
        try:
            code,out,err=adb("mdns","services")
            services=[line.split() for line in out.splitlines() if "_adb-tls-" in line]
            if paired_ip is None:
                pairing=next((row for row in services if len(row)>=3 and row[0].split(".")[0]==identity and "_adb-tls-pairing" in row[1]),None)
                if pairing and time.time()-last_attempt>4:
                    last_attempt=time.time()
                    endpoint=pairing[2]
                    status("pairing",endpoint=endpoint)
                    code,out,err=adb("pair",endpoint,password,timeout=15)
                    if code==0 and "Successfully paired" in out:
                        paired_ip=endpoint.rsplit(":",1)[0]
                        status("paired",ip=paired_ip,message=out)
                    else:
                        status("pairing_retry",error=err or out)
            else:
                candidates=[row[2] for row in services if len(row)>=3 and "_adb-tls-connect" in row[1] and row[2].rsplit(":",1)[0]==paired_ip]
                for endpoint in candidates:
                    adb("connect",endpoint,timeout=8)
                code,out,err=adb("devices")
                devices=[row.split()[0] for row in out.splitlines() if len(row.split())==2 and row.split()[1]=="device"]
                target=next((serial for serial in devices if serial in candidates or serial.startswith(paired_ip+":")),None)
                if target is None:
                    target=next((serial for serial in devices if any(row[0] in serial for row in services if len(row)>=3 and row[2] in candidates)),None)
                if target:
                    settings_path=ROOT/"config"/"settings.json"
                    settings=json.loads(settings_path.read_text(encoding="utf-8-sig"))
                    settings["adb_path"]=str(ADB)
                    settings["serial"]=target
                    settings_path.write_text(json.dumps(settings,ensure_ascii=False,indent=2),encoding="utf8")
                    status("connected",serial=target,ip=paired_ip)
                    return
        except subprocess.TimeoutExpired:
            status("waiting_for_scan" if paired_ip is None else "paired",note="ADB discovery timeout; retrying")
        except Exception as exc:
            status("error",message=str(exc))
            return
        time.sleep(1)
    status("expired")
    SESSION.unlink(missing_ok=True)

if __name__=="__main__":
    import sys
    if "--listen" in sys.argv: listen()
    else: create()
