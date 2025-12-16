from datetime import datetime
from app.database import notification_collection, user_cols

async def notify(
    user_id: str,
    role: str,
    title: str,
    message: str,
    batch_id: str | None = None,
    category: str = "system"
):
    recipients = []

    # 🔥 FIX: expand ALL_MANUFACTURERS safely
    if user_id == "ALL_MANUFACTURERS":
        async for u in user_cols.find({"role": "Manufacturer"}):
            recipients.append(u["id"])
    else:
        recipients.append(user_id)

    notifications = []
    now = datetime.utcnow()

    for uid in recipients:
        notifications.append({
            "user_id": uid,
            "role": role,
            "title": title,
            "message": message,
            "batch_id": batch_id,
            "category": category,
            "read": False,
            "createdAt": now
        })

    if notifications:
        await notification_collection.insert_many(notifications)
