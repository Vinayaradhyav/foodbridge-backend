import os
import re

path = r"d:\food bridge\frontend\lib\features\ngo\screens\ngo_verification_screen.dart"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace duplicate _handleRejectionNotice and duplicate else if
# Let's search between `_onDbChanged()` and `_proceedToDashboard`
pattern = r"        if \(dbUser\.isVerified.*?void _proceedToDashboard"

replacement = """        if (dbUser.isVerified || !dbUser.isPendingApproval || dbUser.verificationStatus == 'VERIFIED' || dbUser.status == 'active') {
          _proceedToDashboard(dbUser);
        } else if (dbUser.verificationStatus == 'REJECTED' || dbUser.status == 'rejected' || dbUser.status == 'suspended') {
          _handleRejectionNotice();
        }
      } catch (_) {}
    }
  }

  void _handleRejectionNotice() {
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

  void _proceedToDashboard"""

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
if new_content != content:
    with open(path, "w", encoding="utf-8") as f:
        f.write(new_content)
    print("Fixed duplicate _handleRejectionNotice successfully!")
else:
    print("Pattern not matched!")

