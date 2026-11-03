import os

def update():
    path = os.path.join(os.path.dirname(__file__), "..", "app", "api", "auth.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    target = 'if user.get("status") == "rejected" or user.get("verification_status") == "REJECTED":'
    replacement = 'if user.get("status") in ("rejected", "suspended") or user.get("verification_status") in ("REJECTED", "SUSPENDED"):'

    if target in content:
        content = content.replace(target, replacement, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated auth.py rejection & suspension check successfully!")
    else:
        print("Target already updated or not found.")

if __name__ == "__main__":
    update()
