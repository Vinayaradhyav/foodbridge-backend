with open('frontend/lib/core/constants/api_config.dart', 'r', encoding='utf-8') as f:
    c = f.read()

old_t = 'return res.statusCode == 200;'
new_t = 'return res.statusCode == 200 && !res.body.trim().startsWith("<") && res.body.contains("healthy");'

if old_t in c:
    c = c.replace(old_t, new_t, 1)
    with open('frontend/lib/core/constants/api_config.dart', 'w', encoding='utf-8') as f:
        f.write(c)
    print('Patched testEndpoint in api_config.dart!')
else:
    print('Could not find old_t')

