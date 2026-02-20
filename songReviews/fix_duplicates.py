from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017")
col = client["songreviews"]["songs"]

# Find max current code
max_doc = col.find_one(sort=[("code", -1)], projection={"code": 1})
next_code = (max_doc["code"] if max_doc and "code" in max_doc else 0) + 1

pipeline = [
    {"$group": {"_id": "$code", "count": {"$sum": 1}, "ids": {"$push": "$_id"}}},
    {"$match": {"count": {"$gt": 1}}}
]

dupes = list(col.aggregate(pipeline))

for d in dupes:
    code = d["_id"]
    ids = d["ids"]

    # keep the first doc, fix the rest
    for _id in ids[1:]:
        col.update_one({"_id": _id}, {"$set": {"code": int(next_code)}})
        next_code += 1

print("Done. Reassigned duplicates.")
