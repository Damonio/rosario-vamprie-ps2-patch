import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

data = json.load(open('extracted_text/strings_executable.json', encoding='utf-8'))
for s in data['strings']:
    ja = s.get('original_ja', '')
    if any(k in ja for k in ['カード', 'データ', '戻り', '読み', '差込', 'セーブ', 'ロード', 'メモリー']):
        print(f"{s['id']:15s} ({s['offset_hex']}): {ja}")
