import re
html = open('/home/z/my-project/download/demo_intro/preview.html').read()
m = re.search(r"<script>\n'use strict';(.*?)</script>", html, re.DOTALL)
if m:
    with open('/tmp/preview_js.js','w') as f:
        f.write("'use strict';\n" + m.group(1))
    print('JS length:', len(m.group(1)))
else:
    print('NOT FOUND')
