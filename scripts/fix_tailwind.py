import os
import re

directory = r"c:\grafity project\goldgen"
html_files = [f for f in os.listdir(directory) if f.endswith('.html')]

for filename in html_files:
    filepath = os.path.join(directory, filename)
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove tailwind.config script block
    content = re.sub(r'<script>\s*tailwind\.config = \{.*?\n\s*\}\s*</script>', '', content, flags=re.DOTALL)
    
    # Remove any remaining tailwind.config related code if it was slightly different
    content = re.sub(r'<script>\s*window\.tailwind\.config = \{.*?\n\s*\}\s*</script>', '', content, flags=re.DOTALL)
    
    # Replace gold- with amber-
    content = content.replace('gold-', 'amber-')
    
    # Add Outfit font to body if not already there and if there's a style block
    if '<style>' in content and 'font-family:' not in content:
        content = content.replace('body {', "body {\n            font-family: 'Outfit', sans-serif;")
        
    # Remove animate-fade-in-up and use standard tailwind or just custom CSS
    # Since we removed tailwind.config which had the keyframes, we should add it to CSS
    if 'animate-fade-in-up' in content and '@keyframes fadeInUp' not in content:
        css_anim = """
        @keyframes fadeInUp {
            0% { opacity: 0; transform: translateY(20px); }
            100% { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in-up {
            animation: fadeInUp 0.6s ease-out forwards;
        }
        """
        content = content.replace('</style>', css_anim + '\n    </style>')

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

print("Processed:", html_files)
