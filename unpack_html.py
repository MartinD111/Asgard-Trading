import json
import base64
import gzip
import os
import sys
from bs4 import BeautifulSoup

def unpack(html_path, out_dir):
    with open(html_path, 'r', encoding='utf-8') as f:
        html = f.read()

    soup = BeautifulSoup(html, 'html.parser')
    template_script = soup.find('script', type='__bundler/template')
    if template_script:
        template_content = template_script.string
        with open(os.path.join(out_dir, 'template.html'), 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        template_soup = BeautifulSoup(template_content, 'html.parser')
        babel_scripts = template_soup.find_all('script', type='text/babel')
        for i, script in enumerate(babel_scripts):
            with open(os.path.join(out_dir, f'component_{i}.tsx'), 'w', encoding='utf-8') as f:
                f.write(script.string if script.string else '')

    manifest_script = soup.find('script', type='__bundler/manifest')
    if manifest_script:
        manifest = json.loads(manifest_script.string)
        for uuid, entry in manifest.items():
            data = base64.b64decode(entry['data'])
            if entry.get('compressed'):
                data = gzip.decompress(data)
            
            ext = entry['mime'].split('/')[-1]
            if ext == 'svg+xml': ext = 'svg'
            
            with open(os.path.join(out_dir, f'{uuid}.{ext}'), 'wb') as f:
                f.write(data)

if __name__ == '__main__':
    os.makedirs('extracted_design', exist_ok=True)
    unpack(r'C:\Users\marti\Downloads\Asgard Trading Terminal.html', 'extracted_design')
    print("Extraction complete.")
