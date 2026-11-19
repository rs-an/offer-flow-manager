from copy import deepcopy
from threading import RLock
from uuid import uuid4
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from editor import payload, redistribute, snapshot
from keitaro import call
from models import Campaign, Stream, Session

app = FastAPI(title="Adrobot")
lock = RLock()  # Локальный запуск в одном процессе, включая несколько вкладок.

class CampaignInput(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    country: str = Field(pattern=r"^[A-Z]{2}$")
    offer_id: int = Field(gt=0)
    domain_id: int = Field(gt=0)
    group_id: int = Field(gt=0)
    traffic_source_id: int = Field(gt=0)

class Change(BaseModel):
    offer_id: int = Field(gt=0)
    percent: int | None = Field(default=None, ge=0, le=100)

def required(db, model, id):
    obj = db.get(model, id)
    if obj is None:
        raise HTTPException(404, "Запись не найдена")
    return obj

def streams(db, cid):
    return list(db.scalars(select(Stream).where(Stream.campaign_id == cid).order_by(Stream.id)))

def view(db, cid):
    c = required(db, Campaign, cid)
    return dict(id=c.id, name=c.name, streams=[
        dict(id=s.id, name=s.name, offers=s.draft, dirty=s.draft != s.published)
        for s in streams(db, cid)])

def choices(path):
    return [dict(id=r["id"], name=r.get("name") or r.get("domain") or str(r["id"])) for r in call("GET", path)]

@app.get("/api/options")
def options():
    return dict(domains=choices("domains"), groups=choices("groups?type=campaigns"), sources=choices("traffic_sources"))

@app.get("/api/offers")
def offers(q: str):
    return [r for r in choices("offers") if str(r["id"]) == q or q.casefold() in r["name"].casefold()][:30]

@app.get("/api/campaigns")
def campaigns():
    with Session() as db:
        return [dict(id=c.id, name=c.name) for c in db.scalars(select(Campaign))]

@app.get("/api/campaigns/{cid}")
def campaign(cid: int):
    with Session() as db:
        return view(db, cid)

@app.post("/api/campaigns/{cid}/fetch")
def fetch(cid: int):
    with lock, Session.begin() as db:
        local = streams(db, cid)
        if any(s.draft != s.published for s in local):
            raise HTTPException(409, "Сначала выполните Push или Cancel")
        c = call("GET", f"campaigns/{cid}")
        remote = call("GET", f"campaigns/{cid}/streams")
        names = {r["id"]:r["name"] for r in choices("offers")}
        db.merge(Campaign(id=cid, name=c["name"]))
        remote_ids = set()
        for r in remote:
            sid = r["id"]
            remote_ids.add(sid)
            s = db.get(Stream, sid)
            rows = snapshot(r.get("offers") or [], s.published if s else [], names)
            db.merge(Stream(id=sid, campaign_id=cid, name=r["name"], published=rows, draft=rows))
        for s in local:
            if s.id not in remote_ids:
                db.delete(s)
        db.flush()
        return view(db, cid)

@app.post("/api/campaigns")
def create(data: CampaignInput):
    call("GET", f"offers/{data.offer_id}")
    alias = uuid4().hex
    try:
        campaign = call("POST", "campaigns", json=dict(name=data.name, alias=alias,
            domain_id=data.domain_id, group_id=str(data.group_id), traffic_source_id=data.traffic_source_id,
            type="position", state="disabled"))
    except HTTPException as exc:
        raise HTTPException(exc.status_code,
            f"Создание не подтверждено. Перед повтором проверьте в Keitaro кампанию "
            f"«{data.name}» с alias {alias}. {exc.detail}") from exc

    cid = campaign["id"]
    progress = "создана. Проверьте в Keitaro поток страны."
    try:
        call("POST", "streams", json=dict(campaign_id=cid, name=data.country, position=1,
            type="regular", state="active", schema="redirect", action_type="http",
            action_payload="https://www.google.com/", filters=[dict(name="country", mode="accept", payload=[data.country])]))
        progress = "создана, поток страны готов. Проверьте в Keitaro поток с оффером."
        call("POST", "streams", json=dict(campaign_id=cid, name="Офферы", position=2,
            type="default", state="active", action_type="http", schema="landings", offers=[
                dict(offer_id=data.offer_id, share=100, state="active")]))
        progress = "создана с обоими потоками. Проверьте в Keitaro, включена ли кампания."
        call("POST", f"campaigns/{cid}/enable")
        progress = "включена. Откройте «Кампании», введите её ID и нажмите «Загрузить потоки»."
        return fetch(cid)
    except HTTPException as exc:
        raise HTTPException(exc.status_code, f"Кампания #{cid} {progress} {exc.detail}") from exc

@app.post("/api/streams/{sid}/offers/{action}")
def edit(sid: int, action: str, data: Change):
    with lock, Session.begin() as db:
        s = required(db, Stream, sid)
        rows = deepcopy(s.draft)
        row = next((r for r in rows if r["id"] == data.offer_id), None)
        if action == "add":
            if not rows or row:
                raise HTTPException(422, "Поток без офферов или связь уже существует")
            offer = call("GET", f"offers/{data.offer_id}")
            rows.append(dict(id=data.offer_id, name=offer["name"], state="active", pin=False, share=0))
        elif row and action == "restore" and row["state"] == "removed":
            row.update(state="active", pin=False)
        elif row and action == "remove" and row["state"] != "removed":
            row.update(state="removed", share=0, pin=False)
        elif row and action in ("lock", "unlock") and row["state"] == "active":
            pinned = action == "lock"
            row["pin"] = pinned
            published = deepcopy(s.published)
            for saved in published:
                if saved["id"] == row["id"] and saved["state"] == "active":
                    saved["pin"] = pinned
            s.published = published
            s.draft = rows
            return view(db, s.campaign_id)
        elif row and action == "pin" and row["state"] == "active":
            row["pin"] = data.percent is not None
            if row["pin"]:
                row["share"] = data.percent
        else:
            raise HTTPException(422, "Действие недоступно")
        redistribute(rows)
        s.draft = rows
        return view(db, s.campaign_id)

@app.post("/api/streams/{sid}/cancel")
def cancel(sid: int):
    with lock, Session.begin() as db:
        s = required(db, Stream, sid)
        s.draft = deepcopy(s.published)
        return view(db, s.campaign_id)

@app.post("/api/streams/{sid}/push")
def push(sid: int):
    with lock, Session.begin() as db:
        s = required(db, Stream, sid)
        remote = call("GET", f"streams/{sid}")
        actual = payload(snapshot(remote.get("offers") or [], [], {}))
        target = payload(s.draft)
        if actual != target:
            if actual != payload(s.published):
                raise HTTPException(409, "Поток изменился в Keitaro. Для загрузки изменений выполните Cancel и Fetch.")
            call("PUT", f"streams/{sid}", json={"offers":target})
        s.published = deepcopy(s.draft)
        return view(db, s.campaign_id)
