import os, re, json, subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

SCOPES=["https://www.googleapis.com/auth/youtube","https://www.googleapis.com/auth/youtube.force-ssl"]

def data_dir():
    p=Path(os.getenv("APP_DATA_DIR",str(Path.home()/".shorts_ai_scheduler"))); p.mkdir(parents=True,exist_ok=True); return p

class YouTube:
    client=data_dir()/"client_secret.json"; token=data_dir()/"token.json"
    @classmethod
    def start(cls):
        uri=os.getenv("GOOGLE_REDIRECT_URI","")
        if not uri: raise RuntimeError("Set GOOGLE_REDIRECT_URI in host environment.")
        if not cls.client.exists(): raise RuntimeError("Upload OAuth Web application JSON in Settings.")
        f=Flow.from_client_secrets_file(str(cls.client),scopes=SCOPES,redirect_uri=uri)
        url,state=f.authorization_url(access_type="offline",prompt="consent",include_granted_scopes="true")
        return url,state
    @classmethod
    def finish(cls,code,state):
        uri=os.getenv("GOOGLE_REDIRECT_URI","")
        f=Flow.from_client_secrets_file(str(cls.client),scopes=SCOPES,state=state,redirect_uri=uri)
        f.fetch_token(code=code); cls.token.write_text(f.credentials.to_json(),encoding="utf-8")
    def __init__(self):
        self.api=None
        if self.token.exists():
            c=Credentials.from_authorized_user_file(str(self.token),SCOPES)
            if c.expired and c.refresh_token: c.refresh(Request()); self.token.write_text(c.to_json(),encoding="utf-8")
            if c.valid: self.api=build("youtube","v3",credentials=c,cache_discovery=False)
        if self.api is None: raise RuntimeError("Authorize YouTube in Settings.")
    def uploads(self):
        c=self.api.channels().list(part="contentDetails",mine=True).execute()["items"][0]
        pl=c["contentDetails"]["relatedPlaylists"]["uploads"]; out=[]; token=None
        while True:
            r=self.api.playlistItems().list(part="snippet,contentDetails",playlistId=pl,maxResults=50,pageToken=token).execute()
            ids=[x["contentDetails"]["videoId"] for x in r.get("items",[])]
            if ids:
                d=self.api.videos().list(part="snippet,status,contentDetails",id=",".join(ids),maxResults=50).execute()
                for v in d.get("items",[]): out.append({"id":v["id"],"title":v["snippet"].get("title",""),"description":v["snippet"].get("description",""),"privacy":v["status"].get("privacyStatus",""),"publishAt":v["status"].get("publishAt",""),"duration":v["contentDetails"].get("duration","")})
            token=r.get("nextPageToken")
            if not token: break
        return out
    def captions(self,vid):
        tracks=self.api.captions().list(part="snippet",videoId=vid).execute().get("items",[])
        if not tracks: return ""
        tracks.sort(key=lambda x:0 if x.get("snippet",{}).get("language")=="ar" else 1)
        raw=self.api.captions().download(id=tracks[0]["id"],tfmt="srt").execute()
        raw=raw.decode("utf-8",errors="ignore") if isinstance(raw,bytes) else str(raw)
        return re.sub(r"(?m)^\s*\d+\s*$|^\d{2}:\d{2}:\d{2}[,.]\d+\s+-->.*$|<[^>]+>","",raw).strip()
    def schedule(self,vid,title,desc,publish_at):
        v=self.api.videos().list(part="snippet,status",id=vid).execute().get("items",[])
        if not v: raise RuntimeError("Video not found.")
        x=v[0]; s=x["status"]
        if s.get("privacyStatus")!="private": raise RuntimeError("Video must be private.")
        if s.get("publishAt"): raise RuntimeError("Already scheduled.")
        x["snippet"]["title"]=title[:100]; x["snippet"]["description"]=desc[:5000]
        s["privacyStatus"]="private"
        dt=datetime.fromisoformat(publish_at)
        s["publishAt"]=dt.astimezone(ZoneInfo("UTC")).isoformat(timespec="seconds").replace("+00:00","Z")
        return self.api.videos().update(part="snippet,status",body={"id":vid,"snippet":x["snippet"],"status":s}).execute()

class LocalWriter:
    def __init__(self,model):
        os.environ["HF_HOME"]=str(data_dir()/"hf_cache")
        self.tok=AutoTokenizer.from_pretrained(model)
        self.model=AutoModelForCausalLM.from_pretrained(model,torch_dtype=torch.float32,low_cpu_mem_usage=True)
        self.model.eval()
    def make(self,title,desc,transcript):
        prompt=f"""أنت محرر عربي لفيديوهات YouTube Shorts. اعتمد فقط على النص المتاح. لا تخترع أحاديث أو آيات أو مراجع أو أحكاما شرعية. أخرج JSON فقط بالمفتاحين title و description. عنوان أقل من 100 حرف ووصف موجز مع هاشتاغات.
العنوان الأصلي: {title}
الوصف الأصلي: {desc[:900]}
النص: {transcript[:4000]}"""
        x=self.tok(prompt,return_tensors="pt",truncation=True,max_length=1600)
        with torch.no_grad(): y=self.model.generate(**x,max_new_tokens=200,do_sample=False,pad_token_id=self.tok.eos_token_id)
        txt=self.tok.decode(y[0][x["input_ids"].shape[1]:],skip_special_tokens=True)
        m=re.search(r"\{.*\}",txt,re.S)
        if m:
            try:
                obj=json.loads(m.group(0)); return {"title":str(obj.get("title",title))[:100],"description":str(obj.get("description",""))[:5000]}
            except Exception: pass
        return {"title":title[:100],"description":txt[:5000]}

class LocalASR:
    def __init__(self,model):
        os.environ["HF_HOME"]=str(data_dir()/"hf_cache")
        self.pipe=pipeline("automatic-speech-recognition",model=model,device=-1)
    def run(self,path):
        wav=Path(path).with_suffix(".wav")
        subprocess.run(["ffmpeg","-y","-i",str(path),"-vn","-ac","1","-ar","16000",str(wav)],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        return self.pipe(str(wav),chunk_length_s=25,stride_length_s=5).get("text","")
