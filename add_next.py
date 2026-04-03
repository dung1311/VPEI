import re
with open("routers/admin.py", "r", encoding="utf-8") as f:
    content = f.read()

# add next_url: str = Query(None) in toggle/delete/create
# Wait, actually, let's just make the forms in settings.html post via fetch if we don't want to change admin.py!
