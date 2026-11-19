from fastapi import HTTPException

def redistribute(rows):
    active = sorted((r for r in rows if r["state"] == "active"), key=lambda r: r["id"])
    free = [r for r in active if not r["pin"]]
    rest = 100 - sum(r["share"] for r in active if r["pin"])
    if not active or rest < 0 or (not free and rest):
        raise HTTPException(422, "Нужен активный оффер и распределение ровно 100%")
    if free:
        share, extra = divmod(rest, len(free))
        for index, row in enumerate(free):
            row["share"] = share + int(index < extra)

def payload(rows):
    return sorted((dict(offer_id=r["id"], share=r["share"], state=r["state"])
                   for r in rows if r["state"] != "removed"), key=lambda x: x["offer_id"])

def snapshot(remote, previous, names):
    old = {r["id"]:r for r in previous}
    result = []
    for item in remote:
        oid = item["offer_id"]
        before = old.pop(oid, {})
        result.append(dict(id=oid, name=names.get(oid, str(oid)), share=item["share"],
                           state=item.get("state", "active"), pin=before.get("pin", False)))
    result.extend(dict(r, state="removed", share=0, pin=False) for r in old.values())
    return result
