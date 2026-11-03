import os

path = r"d:\food bridge\frontend\lib\features\admin\screens\admin_registration_requests_screen.dart"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Add import
import_line = "import 'package:frontend/core/services/device_account_storage.dart';\n"
if "package:frontend/core/services/device_account_storage.dart" not in content:
    target_imp = "import 'package:frontend/features/auth/models/user_model.dart';\n"
    if target_imp in content:
        content = content.replace(target_imp, target_imp + import_line, 1)
    else:
        target_imp_crlf = "import 'package:frontend/features/auth/models/user_model.dart';\r\n"
        content = content.replace(target_imp_crlf, target_imp_crlf + import_line.replace("\n", "\r\n"), 1)

# Fix duplicate call
dup_call = "DeviceAccountStorage.removeAccount(user.phone);\n              DeviceAccountStorage.removeAccount(user.phone);"
dup_call_crlf = dup_call.replace("\n", "\r\n")
single_call = "DeviceAccountStorage.removeAccount(user.phone);"

if dup_call_crlf in content:
    content = content.replace(dup_call_crlf, single_call, 1)
elif dup_call in content:
    content = content.replace(dup_call, single_call, 1)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated admin_registration_requests_screen.dart successfully!")

