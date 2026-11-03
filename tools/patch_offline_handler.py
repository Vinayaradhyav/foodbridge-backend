import sys

file_path = 'frontend/lib/features/auth/services/auth_service.dart'
with open(file_path, 'r', encoding='utf-8') as f:
    text = f.read()

sub1 = """final isOffline = raw.toLowerCase().contains('socket') || 

          raw.toLowerCase().contains('timed out') || 

          raw.toLowerCase().contains('connection') ||

          raw.toLowerCase().contains('failed to connect') ||

          raw.isEmpty;"""

rep1 = """final isOffline = raw.toLowerCase().contains('socket') || 
          raw.toLowerCase().contains('timed out') || 
          raw.toLowerCase().contains('connection') ||
          raw.toLowerCase().contains('failed to connect') ||
          raw.toLowerCase().contains('1033') ||
          raw.toLowerCase().contains('format') ||
          raw.toLowerCase().contains('html') ||
          raw.toLowerCase().contains('gateway') ||
          raw.contains('<') ||
          raw.isEmpty;"""

text = text.replace(sub1, rep1)

sub2 = "if (e is Exception && !eStr.contains('ClientException') && !eStr.contains('SocketException') && !eStr.contains('TimeoutException') && !eStr.contains('HandshakeException')) {"

rep2 = """final isOfflineOrGateway = eStr.contains('ClientException') || eStr.contains('SocketException') || eStr.contains('TimeoutException') || eStr.contains('HandshakeException') || eStr.contains('FormatException') || eStr.contains('1033') || eStr.contains('<');
      if (e is Exception && !isOfflineOrGateway) {"""

text = text.replace(sub2, rep2)

sub3 = "final Map<String, dynamic> err = jsonDecode(response.body);"
rep3 = """if (response.body.trim().startsWith('<')) {
            throw Exception('Server is temporarily unavailable. Retrying...');
          }
          final Map<String, dynamic> err = jsonDecode(response.body);"""

text = text.replace(sub3, rep3)

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully patched auth_service.dart with robust error handling!')

