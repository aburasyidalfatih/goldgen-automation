import os
import re

directory = r"c:\grafity project\goldgen"
html_files = ['analytics.html', 'app_detail.html', 'dashboard_schedule.html', 'login.html']

for filename in html_files:
    filepath = os.path.join(directory, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if we already added it
    if '/* Anti-FOUC' in content:
        continue
        
    # Inject Anti-FOUC CSS into the style block
    if '<style>' in content:
        fouc_css = "/* Anti-FOUC */\n        body { visibility: hidden; opacity: 0; transition: opacity 0.5s ease; }\n        body.ready { visibility: visible; opacity: 1; }\n"
        content = content.replace('<style>', '<style>\n        ' + fouc_css)
    else:
        # analytics.html might have style block, all of them have style blocks
        pass
        
    # Inject the JS before </body>
    fouc_js = """
    <script>
        // Reveal body smoothly after Tailwind CDN generates the styles
        window.addEventListener('load', () => {
            setTimeout(() => { document.body.classList.add('ready'); }, 100);
        });
    </script>
</body>"""
    content = content.replace('</body>', fouc_js)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Added Anti-FOUC to:", html_files)
