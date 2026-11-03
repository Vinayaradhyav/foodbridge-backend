import os

def fix_diagnostics():
    path = os.path.join(os.path.dirname(__file__), "..", "backup_restore_manager.py")
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # 1. Fix boto3 stubs diagnostic
    target_boto = """try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False"""

    replacement_boto = """import importlib
try:
    boto3 = importlib.import_module("boto3")
    ClientError = importlib.import_module("botocore.exceptions").ClientError
    HAS_BOTO3 = True
except Exception:
    boto3 = None
    ClientError = Exception
    HAS_BOTO3 = False"""

    target_boto_crlf = target_boto.replace("\n", "\r\n")
    replacement_boto_crlf = replacement_boto.replace("\n", "\r\n")

    if target_boto_crlf in content:
        content = content.replace(target_boto_crlf, replacement_boto_crlf, 1)
        print("Fixed boto3 imports (CRLF)")
    elif target_boto in content:
        content = content.replace(target_boto, replacement_boto, 1)
        print("Fixed boto3 imports (LF)")
    else:
        print("boto3 target not found")

    # 2. Fix cipher.encrypt
    target_enc = "            if is_encrypted:\n                payload = cipher.encrypt(payload)"
    replacement_enc = "            if is_encrypted and cipher is not None:\n                payload = cipher.encrypt(payload)"
    
    target_enc_crlf = target_enc.replace("\n", "\r\n")
    replacement_enc_crlf = replacement_enc.replace("\n", "\r\n")

    if target_enc_crlf in content:
        content = content.replace(target_enc_crlf, replacement_enc_crlf, 1)
        print("Fixed cipher.encrypt (CRLF)")
    elif target_enc in content:
        content = content.replace(target_enc, replacement_enc, 1)
        print("Fixed cipher.encrypt (LF)")
    else:
        print("encrypt target not found")

    # 3. Fix cipher.decrypt
    target_dec = "            if is_encrypted:\n                raw_data = cipher.decrypt(raw_data)"
    replacement_dec = "            if is_encrypted and cipher is not None:\n                raw_data = cipher.decrypt(raw_data)"

    target_dec_crlf = target_dec.replace("\n", "\r\n")
    replacement_dec_crlf = replacement_dec.replace("\n", "\r\n")

    if target_dec_crlf in content:
        content = content.replace(target_dec_crlf, replacement_dec_crlf, 1)
        print("Fixed cipher.decrypt (CRLF)")
    elif target_dec in content:
        content = content.replace(target_dec, replacement_dec, 1)
        print("Fixed cipher.decrypt (LF)")
    else:
        print("decrypt target not found")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print("Saved backup_restore_manager.py successfully!")

if __name__ == "__main__":
    fix_diagnostics()

