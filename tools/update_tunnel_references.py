import os
import re

tunnel_url = "https://surprised-separately-thing-minimum.trycloudflare.com"

# Update frontend/lib/core/constants/api_config.dart
api_config_path = r"d:\food bridge\frontend\lib\core\constants\api_config.dart"
if os.path.exists(api_config_path):
    with open(api_config_path, "r", encoding="utf-8") as f:
        content = f.read()
    content = re.sub(r"publicTunnelUrl = '[^']+';", f"publicTunnelUrl = '{tunnel_url}';", content)
    with open(api_config_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated api_config.dart")

# Update start_server.bat
start_server_path = r"d:\food bridge\start_server.bat"
if os.path.exists(start_server_path):
    with open(start_server_path, "r", encoding="utf-8") as f:
        bat_content = f.read()
    bat_content = re.sub(r"Current Public HTTPS Tunnel: https://[^\s\r\n]+", f"Current Public HTTPS Tunnel: {tunnel_url}", bat_content)
    with open(start_server_path, "w", encoding="utf-8") as f:
        f.write(bat_content)
    print("Updated start_server.bat")

# Update verify_all_user_requirements.py
verify_script = r"d:\food bridge\backend\tools\verify_all_user_requirements.py"
if os.path.exists(verify_script):
    with open(verify_script, "r", encoding="utf-8") as f:
        v_content = f.read()
    v_content = re.sub(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com", tunnel_url, v_content)
    with open(verify_script, "w", encoding="utf-8") as f:
        f.write(v_content)
    print("Updated verify_all_user_requirements.py")

