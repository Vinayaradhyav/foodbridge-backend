import os

def update_auth_service():
    path = r"d:\food bridge\frontend\lib\features\auth\services\auth_service.dart"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    needle = "// Verify password if user has password recorded"
    guard = """// Immediate rejection & suspension guard
      if (user.status == 'rejected' || user.verificationStatus == 'REJECTED' || user.status == 'suspended') {
        throw Exception("Your account application has been rejected or suspended by administration. Please contact support.");
      }

      """

    if needle in content:
        content = content.replace(needle, guard + needle, 1)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("Updated auth_service.dart successfully!")
        return True
    else:
        print("Needle not found in auth_service.dart")
        return False

def update_ngo_verification_screen():
    path = r"d:\food bridge\frontend\lib\features\ngo\screens\ngo_verification_screen.dart"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # In _startPeriodicApprovalCheck():
    # If refreshed is REJECTED, cancel timer and show rejection notice
    target = """        if (refreshed != null && (refreshed.isVerified || !refreshed.isPendingApproval || refreshed.verificationStatus == 'VERIFIED' || refreshed.status == 'active')) {
          timer.cancel();
          if (mounted) {
            _proceedToDashboard(refreshed);
          }
        }"""
    target_crlf = target.replace("\n", "\r\n")

    replacement = """        if (refreshed != null && (refreshed.isVerified || !refreshed.isPendingApproval || refreshed.verificationStatus == 'VERIFIED' || refreshed.status == 'active')) {
          timer.cancel();
          if (mounted) {
            _proceedToDashboard(refreshed);
          }
        } else if (refreshed != null && (refreshed.verificationStatus == 'REJECTED' || refreshed.status == 'rejected' || refreshed.status == 'suspended')) {
          timer.cancel();
          if (mounted) {
            _handleRejectionNotice();
          }
        }"""
    replacement_crlf = replacement.replace("\n", "\r\n")

    if target_crlf in content:
        content = content.replace(target_crlf, replacement_crlf, 1)
    elif target in content:
        content = content.replace(target, replacement, 1)
    else:
        print("Target periodic check not found in ngo_verification_screen.dart")

    # In _onDbChanged():
    target2 = """        if (dbUser.isVerified || !dbUser.isPendingApproval || dbUser.verificationStatus == 'VERIFIED' || dbUser.status == 'active') {
          _proceedToDashboard(dbUser);
        }"""
    target2_crlf = target2.replace("\n", "\r\n")

    replacement2 = """        if (dbUser.isVerified || !dbUser.isPendingApproval || dbUser.verificationStatus == 'VERIFIED' || dbUser.status == 'active') {
          _proceedToDashboard(dbUser);
        } else if (dbUser.verificationStatus == 'REJECTED' || dbUser.status == 'rejected' || dbUser.status == 'suspended') {
          _handleRejectionNotice();
        }"""
    replacement2_crlf = replacement2.replace("\n", "\r\n")

    if target2_crlf in content:
        content = content.replace(target2_crlf, replacement2_crlf, 1)
    elif target2 in content:
        content = content.replace(target2, replacement2, 1)
    else:
        print("Target db change not found in ngo_verification_screen.dart")

    # Add _handleRejectionNotice method before _proceedToDashboard
    target3 = "  void _proceedToDashboard(dynamic user) {"
    target3_crlf = target3.replace("\n", "\r\n")
    
    rejection_method = """  void _handleRejectionNotice() {
    _pollingTimer?.cancel();
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text("Application Update: Your organization registration was rejected by administrator."),
        backgroundColor: Color(0xFFDC2626),
        duration: Duration(seconds: 4),
      ),
    );
    Navigator.pushNamedAndRemoveUntil(context, AppRoutes.login, (route) => false);
  }

  void _proceedToDashboard(dynamic user) {"""
    rejection_method_crlf = rejection_method.replace("\n", "\r\n")

    if target3_crlf in content:
        content = content.replace(target3_crlf, rejection_method_crlf, 1)
    elif target3 in content:
        content = content.replace(target3, rejection_method, 1)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Updated ngo_verification_screen.dart successfully!")
    return True

def update_account_deletion_purge():
    # Update admin_users_screen.dart and admin_registration_requests_screen.dart to purge DeviceAccountStorage
    path1 = r"d:\food bridge\frontend\lib\features\admin\screens\admin_users_screen.dart"
    with open(path1, "r", encoding="utf-8") as f:
        c1 = f.read()
    
    target1 = "MockDatabase.users.removeWhere((item) => item.id == u.id || item.firebaseUid == u.firebaseUid);\n                    await MockDatabase.saveUsersToStorage();"
    target1_crlf = target1.replace("\n", "\r\n")
    replacement1 = "MockDatabase.users.removeWhere((item) => item.id == u.id || item.firebaseUid == u.firebaseUid);\n                    await MockDatabase.saveUsersToStorage();\n                    await DeviceAccountStorage.removeAccount(u.phone);"
    replacement1_crlf = replacement1.replace("\n", "\r\n")

    if target1_crlf in c1:
        c1 = c1.replace(target1_crlf, replacement1_crlf, 1)
        with open(path1, "w", encoding="utf-8") as f:
            f.write(c1)
        print("Updated admin_users_screen.dart with DeviceAccountStorage purge!")
    elif target1 in c1:
        c1 = c1.replace(target1, replacement1, 1)
        with open(path1, "w", encoding="utf-8") as f:
            f.write(c1)
        print("Updated admin_users_screen.dart with DeviceAccountStorage purge!")

    path2 = r"d:\food bridge\frontend\lib\features\admin\screens\admin_registration_requests_screen.dart"
    with open(path2, "r", encoding="utf-8") as f:
        c2 = f.read()

    target2 = "MockDatabase.users.removeWhere((u) => u.id == user.id || u.firebaseUid == user.firebaseUid || (user.phone.isNotEmpty && u.phone == user.phone));\n              MockDatabase.saveUsersToStorage();\n              MockDatabase.notifyChange();"
    target2_crlf = target2.replace("\n", "\r\n")
    replacement2 = "MockDatabase.users.removeWhere((u) => u.id == user.id || u.firebaseUid == user.firebaseUid || (user.phone.isNotEmpty && u.phone == user.phone));\n              MockDatabase.saveUsersToStorage();\n              MockDatabase.notifyChange();\n              DeviceAccountStorage.removeAccount(user.phone);"
    replacement2_crlf = replacement2.replace("\n", "\r\n")

    if target2_crlf in c2:
        c2 = c2.replace(target2_crlf, replacement2_crlf, 1)
        with open(path2, "w", encoding="utf-8") as f:
            f.write(c2)
        print("Updated admin_registration_requests_screen.dart with DeviceAccountStorage purge!")
    elif target2 in c2:
        c2 = c2.replace(target2, replacement2, 1)
        with open(path2, "w", encoding="utf-8") as f:
            f.write(c2)
        print("Updated admin_registration_requests_screen.dart with DeviceAccountStorage purge!")

if __name__ == "__main__":
    update_auth_service()
    update_ngo_verification_screen()
    update_account_deletion_purge()
