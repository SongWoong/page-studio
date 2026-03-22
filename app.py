import os
import json
import uuid
import re
import base64
from datetime import datetime
from flask import Flask, request, jsonify, render_template, send_file, abort, Response
from anthropic import Anthropic
from dotenv import load_dotenv

# .env 직접 읽기 (Python 3.14 dotenv 호환 문제 우회)
_env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
if os.path.exists(_env_path):
    with open(_env_path, encoding='utf-8') as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PAGES_FOLDER'] = 'data/pages'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['PAGES_FOLDER'], exist_ok=True)

_default_api_key = os.environ.get('ANTHROPIC_API_KEY', '')

def get_client():
    """요청 헤더의 API 키 우선, 없으면 서버 환경변수 사용"""
    key = request.headers.get('X-API-Key', '').strip() or _default_api_key
    return Anthropic(api_key=key)


@app.errorhandler(500)
def handle_500(e):
    import traceback
    tb = traceback.format_exc()
    print("=== 500 ERROR ===")
    print(tb)
    return jsonify({"error": str(e), "traceback": tb}), 500

@app.route('/')
def index():
    return render_template('index.html')


# 섹션 풀 (순서 있음 - 앞에서부터 page_count개 선택, 마지막은 항상 CTA)
ALL_SECTIONS = [
    ("헤드라인", "독자를 단번에 사로잡는 강렬한 카피 (30자 내외)"),
    ("공감 문구", "독자의 고민/상황에 공감하는 감성적 문구 (60-100자)"),
    ("문제 제기", "독자가 겪는 핵심 문제를 구체적으로 묘사 (100-150자)"),
    ("책 소개", "이 책이 무엇인지, 왜 특별한지 설득력 있게 (150-200자)"),
    ("핵심 내용", "책에서 얻을 수 있는 핵심 내용 4가지 (각 제목+설명 1줄)"),
    ("저자 소개", "저자의 신뢰도와 전문성을 부각 (100-130자)"),
    ("추천 독자", "이 책이 꼭 필요한 독자 유형 4가지 (간결하게)"),
    ("독자 후기", "실제 독자 후기 2개 (각 60-80자, 이름 포함)"),
    ("책 목차 미리보기", "주요 챕터 제목과 간략한 설명"),
    ("이 책만의 차별점", "다른 책과 다른 이 책만의 강점 3가지"),
    ("기대 효과", "이 책을 읽은 전/후 변화 (Before → After 형식)"),
    ("전문가 추천사", "전문가·언론의 추천 문구 2개"),
    ("FAQ", "구매 전 자주 묻는 질문 3가지와 답변"),
    ("특별 부록 안내", "책과 함께 제공되는 부록/보너스 내용"),
    ("베스트셀러 성과", "판매 실적, 수상 내역, 언론 보도"),
    ("독자 Q&A", "독자 질문과 저자 답변 2개"),
    ("저자의 메시지", "독자에게 보내는 진심 어린 메시지 (100자 내외)"),
    ("함께 읽으면 좋은 책", "저자가 추천하는 관련 도서 3권"),
    ("구매 혜택", "지금 구매해야 하는 이유 3가지 (구체적으로)"),
    ("구매 CTA", "구매를 유도하는 마지막 강력한 한 마디 (30-50자)"),
]
CTA_SECTION = ("구매 CTA", "구매를 유도하는 마지막 강력한 한 마디 (30-50자)")


def build_section_list(page_count):
    """page_count에 맞게 섹션 선택. 마지막은 항상 CTA."""
    page_count = max(3, min(20, page_count))
    non_cta = [s for s in ALL_SECTIONS if s[0] != "구매 CTA"]
    chosen = non_cta[:page_count - 1]
    chosen.append(CTA_SECTION)
    return chosen


@app.route('/api/generate-copy', methods=['POST'])
def generate_copy():
    data = request.json
    title = data.get('title', '')
    author = data.get('author', '')
    genre = data.get('genre', '')
    target = data.get('target', '')
    key_message = data.get('key_message', '')
    selling_points = data.get('selling_points', '')
    price = data.get('price', '')
    page_count = int(data.get('page_count', 10))

    section_list = build_section_list(page_count)
    sections_desc = "\n".join([
        f"{i+1}. {name}: {desc}"
        for i, (name, desc) in enumerate(section_list)
    ])
    json_items = ",\n    ".join([
        f'{{"id": {i+1}, "title": "{name}", "content": "..."}}'
        for i, (name, _) in enumerate(section_list)
    ])

    prompt = f"""당신은 책 마케팅 전문 카피라이터입니다.
아래 책 정보를 바탕으로 온라인 서점 상세페이지에 사용할 {page_count}개 섹션의 마케팅 멘트를 작성해주세요.

책 정보:
- 제목: {title}
- 저자: {author}
- 장르/분야: {genre}
- 타겟 독자: {target}
- 핵심 메시지: {key_message}
- 판매 포인트: {selling_points}
- 가격: {price}

{page_count}개 섹션 구성:
{sections_desc}

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "sections": [
    {json_items}
  ]
}}"""

    try:
        response = get_client().messages.create(
            model="claude-opus-4-6",
            max_tokens=8000,
            messages=[{"role": "user", "content": prompt}]
        )
        text = response.content[0].text
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            result = json.loads(json_match.group())
        else:
            result = {"sections": [], "error": "파싱 실패"}
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e), "sections": []}), 500


@app.route('/api/analyze-design', methods=['POST'])
def analyze_design():
    files = request.files.getlist('images')
    if not files or all(f.filename == '' for f in files):
        return jsonify({"error": "이미지가 없습니다"}), 400

    # 최대 10장까지
    files = [f for f in files if f.filename != ''][:10]

    # 모든 이미지를 content 블록으로 구성
    content = []
    for f in files:
        image_bytes = f.read()
        image_data = base64.standard_b64encode(image_bytes).decode('utf-8')
        media_type = f.content_type or 'image/jpeg'
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": image_data}
        })

    content.append({
        "type": "text",
        "text": f"""위 {len(files)}장의 이미지는 책 상세페이지 디자인 레퍼런스입니다.

각 이미지의 강점을 개별 분석한 뒤, 모든 이미지에서 가장 효과적인 요소들만 선별하여
최고의 조합으로 새 상세페이지에 적용할 통합 스타일 가이드를 만들어주세요.

분석 기준:
- 어떤 이미지의 색상 조합이 가장 눈에 띄고 세련되었는가
- 어떤 이미지의 타이포그래피가 가장 가독성이 좋은가
- 어떤 이미지의 섹션 구분 방식이 가장 명확한가
- 어떤 이미지의 전체 분위기가 책 마케팅에 가장 효과적인가

이 강점들을 하나로 합쳐 최적의 디자인 방향을 제시하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{{
  "colors": {{
    "primary": "#색상코드",
    "secondary": "#색상코드",
    "background": "#색상코드",
    "text": "#색상코드",
    "accent": "#색상코드",
    "section_bg": "#섹션배경색"
  }},
  "tone": "디자인 톤 (예: 모던 미니멀, 따뜻한 클래식, 고급스러운 다크, 밝고 경쾌한 등)",
  "typography": "폰트 스타일 (크기, 굵기, 행간 특징)",
  "layout": "레이아웃 구조 (섹션 너비, 여백, 정렬 방식)",
  "section_style": "각 섹션의 구분 방식 (배경색 교체, 구분선, 카드 등)",
  "elements": "주요 디자인 요소 (아이콘, 뱃지, 버튼 스타일 등)",
  "mood": "전반적인 분위기와 감성",
  "css_hints": "CSS 구현 핵심 포인트 (그라디언트, 그림자, 둥글기 등 구체적으로)",
  "best_from": "각 이미지에서 채택한 요소 요약 (예: 1번-색상, 2번-타이포, 3번-레이아웃)"
}}"""
    })

    response = get_client().messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": content}]
    )

    text = response.content[0].text
    json_match = re.search(r'\{[\s\S]*\}', text)
    if json_match:
        analysis = json.loads(json_match.group())
    else:
        analysis = {"tone": "모던 미니멀", "colors": {"primary": "#2c3e50", "background": "#ffffff", "text": "#333333", "accent": "#e74c3c", "secondary": "#7f8c8d", "section_bg": "#f8f9fa"}}

    return jsonify({"analysis": analysis})


@app.route('/api/create-page', methods=['POST'])
def create_page():
    data = request.json
    book_info = data.get('book_info', {})
    sections = data.get('sections', [])
    design_analysis = data.get('design_analysis', None)

    sections_text = "\n".join([
        f"[섹션 {s['id']} - {s['title']}]\n{s['content']}"
        for s in sections
    ])

    if design_analysis:
        colors = design_analysis.get('colors', {})
        design_prompt = f"""디자인 레퍼런스를 분석한 결과를 반드시 반영하세요:
- 주 색상: {colors.get('primary', '#2c3e50')}
- 보조 색상: {colors.get('secondary', '#7f8c8d')}
- 배경 색상: {colors.get('background', '#ffffff')}
- 텍스트 색상: {colors.get('text', '#333333')}
- 강조 색상: {colors.get('accent', '#e74c3c')}
- 디자인 톤: {design_analysis.get('tone', '')}
- 타이포그래피: {design_analysis.get('typography', '')}
- 레이아웃: {design_analysis.get('layout', '')}
- 분위기: {design_analysis.get('mood', '')}
- CSS 힌트: {design_analysis.get('css_hints', '')}"""
    else:
        design_prompt = """깔끔하고 전문적인 모던 스타일로 디자인하세요.
- 주 색상: #1a1a2e, 강조색: #e94560, 배경: #ffffff
- 섹션마다 시각적으로 명확히 구분되게 해주세요."""

    title = book_info.get('title', '제목 없음')
    author = book_info.get('author', '')
    price = book_info.get('price', '')
    page_count = len(sections)

    # 섹션별 내용 텍스트
    sections_text = "\n\n".join([
        f"[섹션 {s['id']} - {s['title']}]\n{s['content']}"
        for s in sections
    ])

    # 섹션별 HTML 힌트 (제목으로 스타일 추론)
    def get_section_hint(title_str, idx):
        t = title_str
        if idx == 1 or '헤드라인' in t:
            return f"섹션{idx} ({t}): 풀너비 진한 배경, 책 제목 크게, 저자명, 헤드라인 카피"
        elif '공감' in t:
            return f"섹션{idx} ({t}): 부드러운 배경, 큰 인용구 스타일 중앙 정렬 문구"
        elif '문제' in t:
            return f"섹션{idx} ({t}): 독자 고민을 리스트 또는 강조 텍스트로"
        elif '핵심 내용' in t or '내용' in t:
            return f"섹션{idx} ({t}): 2×2 카드 그리드, 이모지 아이콘 포함"
        elif '저자' in t and '메시지' not in t:
            return f"섹션{idx} ({t}): 이니셜 원형 아바타, 소개 텍스트"
        elif '추천 독자' in t:
            return f"섹션{idx} ({t}): ✅ 체크마크 리스트 4개"
        elif '후기' in t or 'Q&A' in t and '독자' in t:
            return f"섹션{idx} ({t}): 큰따옴표(❝❞) 후기 카드, 이름+별점"
        elif '혜택' in t:
            return f"섹션{idx} ({t}): 이모지+혜택 3개 가로 나열"
        elif 'CTA' in t or (idx == page_count):
            return f"섹션{idx} ({t}): 강렬한 배경색, 풀너비 큰 구매 버튼, 가격 표시"
        elif '목차' in t:
            return f"섹션{idx} ({t}): 넘버링된 챕터 목록"
        elif '차별점' in t:
            return f"섹션{idx} ({t}): 포인트 카드 3개"
        elif '효과' in t or 'Before' in t:
            return f"섹션{idx} ({t}): Before→After 2단 구성"
        elif '추천사' in t or '전문가' in t:
            return f"섹션{idx} ({t}): 인용구 카드 + 추천인 이름"
        elif 'FAQ' in t:
            return f"섹션{idx} ({t}): Q&A 스타일, Q는 굵게 A는 보통"
        elif '부록' in t:
            return f"섹션{idx} ({t}): 선물 박스 스타일, 혜택 리스트"
        elif '성과' in t or '베스트' in t:
            return f"섹션{idx} ({t}): 숫자 강조 배지, 수치 크게"
        elif '메시지' in t:
            return f"섹션{idx} ({t}): 따뜻한 배경, 감성적 인용구 스타일"
        else:
            return f"섹션{idx} ({t}): 깔끔한 텍스트 블록, 내용에 맞게 시각적으로"

    section_hints = "\n".join([
        get_section_hint(s['title'], s['id']) for s in sections
    ])

    prompt = f"""당신은 한국 온라인 서점 상세페이지(스마트스토어/쿠팡 스타일)를 만드는 전문 웹 디자이너입니다.
아래 내용으로 완성도 높은 상세페이지 HTML을 만드세요.

{design_prompt}

책 정보:
- 제목: {title}
- 저자: {author}
- 가격: {price}

총 {page_count}개 섹션 마케팅 멘트:
{sections_text}

각 섹션의 시각적 스타일 가이드:
{section_hints}

HTML 구조 요구사항:
- 모든 {page_count}개 섹션을 순서대로 빠짐없이 구현할 것
- 각 섹션은 <section> 태그로 감싸고 시각적으로 완전히 구분
- 섹션마다 배경색을 번갈아 달리 (흰색↔섹션배경색)
- 전체 너비 max-width: 680px, 가운데 정렬
- 각 섹션 padding: 최소 60px 40px
- 카드형 요소: border-radius 12px 이상, box-shadow 적용
- 마지막 CTA 섹션: 강렬한 배경, 풀너비 버튼, 가격 크게
- 모바일 반응형 필수 (max-width: 480px 미디어쿼리)
- 구글 폰트 Noto Sans KR 사용

<!DOCTYPE html>부터 시작하는 완전한 HTML만 응답. 마크다운 코드블록 없이."""

    response = get_client().messages.create(
        model="claude-opus-4-6",
        max_tokens=16000,
        messages=[{"role": "user", "content": prompt}]
    )

    html_content = response.content[0].text

    # 마크다운 코드블록 제거
    if html_content.strip().startswith('```'):
        lines = html_content.strip().split('\n')
        start = 1
        end = len(lines)
        if lines[-1].strip() == '```':
            end = len(lines) - 1
        html_content = '\n'.join(lines[start:end])

    # 다운로드 툴바 HTML (html2canvas + jsPDF 사용, 인쇄 시 숨김)
    download_toolbar = f"""<style>
#ps-toolbar{{position:fixed;top:0;left:0;right:0;z-index:9999;background:rgba(20,20,40,0.95);
backdrop-filter:blur(8px);display:flex;align-items:center;justify-content:center;
gap:10px;padding:10px 20px;box-shadow:0 2px 12px rgba(0,0,0,0.3)}}
#ps-toolbar span{{color:#fff;font-size:13px;font-weight:600;margin-right:8px;font-family:'Noto Sans KR',sans-serif}}
.ps-btn{{padding:8px 18px;border:none;border-radius:8px;font-size:13px;font-weight:700;
cursor:pointer;transition:all 0.2s;font-family:'Noto Sans KR',sans-serif}}
.ps-btn:hover{{transform:translateY(-1px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}}
.ps-btn-pdf{{background:linear-gradient(135deg,#e74c3c,#c0392b);color:#fff}}
.ps-btn-png{{background:linear-gradient(135deg,#3498db,#2980b9);color:#fff}}
.ps-btn-jpg{{background:linear-gradient(135deg,#2ecc71,#27ae60);color:#fff}}
.ps-btn-print{{background:linear-gradient(135deg,#9b59b6,#8e44ad);color:#fff}}
body{{padding-top:54px}}
@media print{{#ps-toolbar{{display:none!important}}body{{padding-top:0}}}}
</style>
<div id="ps-toolbar">
  <span>📄 {title}</span>
  <button class="ps-btn ps-btn-pdf" onclick="psDownload('pdf')">⬇ PDF</button>
  <button class="ps-btn ps-btn-png" onclick="psDownload('png')">⬇ PNG</button>
  <button class="ps-btn ps-btn-jpg" onclick="psDownload('jpg')">⬇ JPG</button>
  <button class="ps-btn ps-btn-print" onclick="window.print()">🖨 인쇄</button>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
<script>
async function psDownload(fmt) {{
  const toolbar = document.getElementById('ps-toolbar');
  toolbar.style.display = 'none';
  document.body.style.paddingTop = '0';
  try {{
    const canvas = await html2canvas(document.body, {{
      scale: 2, useCORS: true, allowTaint: true,
      windowWidth: 780, scrollY: 0, height: document.body.scrollHeight
    }});
    if (fmt === 'pdf') {{
      const {{ jsPDF }} = window.jspdf;
      const imgData = canvas.toDataURL('image/jpeg', 0.92);
      const pdf = new jsPDF({{ orientation: 'portrait', unit: 'px', format: [canvas.width/2, canvas.height/2] }});
      pdf.addImage(imgData, 'JPEG', 0, 0, canvas.width/2, canvas.height/2);
      pdf.save('{title}.pdf');
    }} else if (fmt === 'png') {{
      const a = document.createElement('a'); a.href = canvas.toDataURL('image/png');
      a.download = '{title}.png'; a.click();
    }} else {{
      const a = document.createElement('a'); a.href = canvas.toDataURL('image/jpeg', 0.92);
      a.download = '{title}.jpg'; a.click();
    }}
  }} finally {{
    toolbar.style.display = 'flex';
    document.body.style.paddingTop = '54px';
  }}
}}
</script>"""

    # HTML에 툴바 삽입 (<body> 바로 뒤)
    if '<body' in html_content:
        insert_pos = html_content.find('>', html_content.find('<body')) + 1
        html_content = html_content[:insert_pos] + '\n' + download_toolbar + '\n' + html_content[insert_pos:]
    else:
        html_content = download_toolbar + html_content

    # 페이지 저장
    page_id = str(uuid.uuid4())[:8]
    html_path = os.path.join(app.config['PAGES_FOLDER'], f"{page_id}.html")
    meta_path = os.path.join(app.config['PAGES_FOLDER'], f"{page_id}.json")

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    page_meta = {
        "id": page_id,
        "title": book_info.get('title', ''),
        "author": book_info.get('author', ''),
        "created_at": datetime.now().isoformat()
    }
    with open(meta_path, 'w', encoding='utf-8') as f:
        json.dump(page_meta, f, ensure_ascii=False, indent=2)

    return jsonify({"page_id": page_id, "url": f"/view/{page_id}"})


@app.route('/api/download/<page_id>/<fmt>')
def download_page(page_id, fmt):
    """다운로드는 브라우저 클라이언트에서 처리 (html2canvas + jsPDF)"""
    return jsonify({"message": "다운로드는 상세페이지 상단 버튼을 이용해주세요."}), 200


@app.route('/view/<page_id>')
def view_page(page_id):
    # 보안: 경로 조작 방지
    safe_id = re.sub(r'[^a-zA-Z0-9\-]', '', page_id)[:8]
    html_path = os.path.join(app.config['PAGES_FOLDER'], f"{safe_id}.html")
    if not os.path.exists(html_path):
        abort(404)
    return send_file(html_path)


@app.route('/api/pages')
def list_pages():
    pages = []
    folder = app.config['PAGES_FOLDER']
    for filename in os.listdir(folder):
        if filename.endswith('.json'):
            try:
                with open(os.path.join(folder, filename), 'r', encoding='utf-8') as f:
                    pages.append(json.load(f))
            except Exception:
                pass
    pages.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return jsonify(pages)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, use_reloader=False, host='0.0.0.0', port=port)
