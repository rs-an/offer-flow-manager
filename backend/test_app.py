from copy import deepcopy
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import main
from models import Base
from editor import redistribute

@pytest.fixture
def stand(tmp_path, monkeypatch):
    engine = create_engine("sqlite:///" + str(tmp_path / "test.db"))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main, "Session", sessionmaker(engine))
    streams = {}
    requests = []
    fail = set()
    def remote(method, path, json=None):
        requests.append((method, path, json))
        if path in fail:
            raise HTTPException(502, "Ошибка стенда")
        if path == "campaigns": return {"id":1}
        if path == "streams":
            sid = len(streams)+1
            streams[sid] = dict(json, id=sid)
            return streams[sid]
        if path == "campaigns/1/streams": return deepcopy(list(streams.values()))
        if path == "campaigns/1": return dict(id=1,name="test")
        if path == "campaigns/1/enable": return {}
        if path == "offers": return [dict(id=i,name=str(i)) for i in range(1,5)]
        if path.startswith("offers/"): return dict(id=int(path.split('/')[1]),name=path)
        if path.startswith("streams/"):
            s=streams[int(path.split('/')[1])]
            if method=="PUT": s.update(deepcopy(json))
            return deepcopy(s)
        raise AssertionError(path)
    monkeypatch.setattr(main,"call",remote)
    return TestClient(main.app), streams, requests, fail

FORM=dict(name="test", country="AU", offer_id=1, group_id=1, domain_id=1, traffic_source_id=1)

def test_create(stand):
    api, streams, requests, _ = stand
    assert api.post("/api/campaigns",json=FORM).status_code==200
    campaign = next(body for method, path, body in requests if (method, path) == ("POST", "campaigns"))
    assert campaign["type"] == "position"
    assert streams[1]["action_payload"] == "https://www.google.com/"
    assert streams[1]["filters"] == [dict(name="country", mode="accept", payload=["AU"])]
    assert streams[2]["type"] == "default"
    assert streams[2]["offers"][0]["offer_id"] == FORM["offer_id"]
    assert streams[1]["position"] < streams[2]["position"]
    assert streams[2]["offers"][0]["share"]==100

def test_partial_create(stand):
    api, _, _, fail=stand
    fail.add("streams")
    assert "#1" in api.post("/api/campaigns",json=FORM).json()["detail"]

def test_editor(stand):
    api, streams, _, fail=stand
    api.post("/api/campaigns",json=FORM).raise_for_status()
    path="/api/streams/2/"
    def edit(action,oid,**extra):
        return api.post(path+"offers/"+action,json=dict(offer_id=oid,**extra))
    edit("add",2).raise_for_status()
    assert api.post("/api/campaigns/1/fetch").status_code==409
    api.post(path+"cancel").raise_for_status()
    assert len(api.get("/api/campaigns/1").json()["streams"][1]["offers"])==1
    edit("add",2).raise_for_status()
    api.post(path+"push").raise_for_status()
    assert [r["share"] for r in streams[2]["offers"]]==[50,50]
    streams[2]["offers"].pop()
    rows=api.post("/api/campaigns/1/fetch").json()["streams"][1]["offers"]
    assert rows[1]["state"]=="removed"
    for action, pinned in [("lock", True), ("unlock", False)]:
        stream = edit(action, 1).json()["streams"][1]
        assert stream["offers"][0]["pin"] is pinned
        assert stream["offers"][0]["share"] == 50
        assert not stream["dirty"]
        assert api.post("/api/campaigns/1/fetch").json()["streams"][1]["offers"][0]["pin"] is pinned
    edit("restore",2).raise_for_status()
    edit("pin",1,percent=25).raise_for_status()
    edit("add",3).raise_for_status()
    fail.add("streams/2")
    assert api.post(path+"push").status_code==502
    fail.clear()
    streams[2]["offers"][0]["share"]=80
    assert api.post(path+"push").status_code==409
    streams[2]["offers"][0]["share"]=50
    api.post(path+"push").raise_for_status()
    assert [r["share"] for r in streams[2]["offers"]]==[25,38,37]
    edit("remove",3).raise_for_status()
    api.post(path+"push").raise_for_status()
    assert len(streams[2]["offers"])==2

def test_invalid_pins():
    with pytest.raises(HTTPException):
        redistribute([dict(id=1,state="active",share=25,pin=True)])
