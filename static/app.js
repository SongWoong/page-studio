// ===== 상태 =====
let currentStep = 1;
let bookInfo = {};
let sections = [];
let designAnalysis = null;
let selectedFiles = [];
let selectedPageCount = 10;
let userApiKey = '';

// ===== API 키 관리 =====
function initApiKey() {
  const saved = localStorage.getItem('ps_api_key') || sessionStorage.getItem('ps_api_key');
  if (saved) {
    userApiKey = saved;
    document.getElementById('apikey-overlay').classList.add('hidden');
    document.getElementById('btn-change-key').style.display = 'block';
  }
}

function submitApiKey() {
  const input = document.getElementById('apikey-input').value.trim();
  const errEl = document.getElementById('apikey-error');
  errEl.style.display = 'none';

  if (!input) {
    errEl.textContent = 'API 키를 입력해주세요.';
    errEl.style.display = 'block';
    return;
  }
  if (!input.startsWith('sk-ant-')) {
    errEl.textContent = 'Anthropic API 키는 sk-ant- 로 시작해야 해요.';
    errEl.style.display = 'block';
    return;
  }

  userApiKey = input;
  if (document.getElementById('apikey-remember').checked) {
    localStorage.setItem('ps_api_key', input);
  } else {
    sessionStorage.setItem('ps_api_key', input);
  }
  document.getElementById('apikey-overlay').classList.add('hidden');
  document.getElementById('btn-change-key').style.display = 'block';
}

function skipApiKey() {
  userApiKey = '';
  document.getElementById('apikey-overlay').classList.add('hidden');
  document.getElementById('btn-change-key').style.display = 'block';
}

function changeApiKey() {
  userApiKey = '';
  localStorage.removeItem('ps_api_key');
  sessionStorage.removeItem('ps_api_key');
  document.getElementById('apikey-input').value = '';
  document.getElementById('apikey-error').style.display = 'none';
  document.getElementById('apikey-overlay').classList.remove('hidden');
  document.getElementById('btn-change-key').style.display = 'none';
}

function toggleApiKeyVisibility() {
  const inp = document.getElementById('apikey-input');
  inp.type = inp.type === 'password' ? 'text' : 'password';
}

// API 키 포함 fetch 헬퍼
function apiFetch(url, options = {}) {
  options.headers = { ...(options.headers || {}), 'X-API-Key': userApiKey };
  return fetch(url, options);
}

// ===== 초기화 =====
document.addEventListener('DOMContentLoaded', () => {
  initApiKey();
  document.getElementById('book-form').addEventListener('submit', handleBookFormSubmit);
  document.getElementById('apikey-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter') submitApiKey();
  });
  setupDragDrop();
});

// ===== 페이지 수 선택 =====
function setPageCount(n) {
  selectedPageCount = n;
  document.getElementById('f-page-count').value = n;
  document.querySelectorAll('.page-count-btn').forEach(btn => btn.classList.remove('active'));
  event.target.classList.add('active');
}

// ===== 히어로 → 앱 전환 =====
function startFlow() {
  document.getElementById('hero').style.display = 'none';
  document.getElementById('app').style.display = 'block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== 스텝 이동 =====
function goStep(n) {
  // 현재 패널 비활성화
  document.getElementById(`panel-${currentStep}`).classList.remove('active');
  document.getElementById(`step-dot-${currentStep}`).classList.remove('active');
  document.getElementById(`step-dot-${currentStep}`).classList.add('done');

  currentStep = n;

  // 새 패널 활성화
  document.getElementById(`panel-${n}`).classList.add('active');

  // 스텝 인디케이터 업데이트
  for (let i = 1; i <= 4; i++) {
    const dot = document.getElementById(`step-dot-${i}`);
    dot.classList.remove('active', 'done');
    if (i < n) dot.classList.add('done');
    else if (i === n) dot.classList.add('active');
  }

  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== STEP 1: 책 정보 제출 =====
async function handleBookFormSubmit(e) {
  e.preventDefault();

  bookInfo = {
    title: document.getElementById('f-title').value.trim(),
    author: document.getElementById('f-author').value.trim(),
    genre: document.getElementById('f-genre').value.trim(),
    target: document.getElementById('f-target').value.trim(),
    key_message: document.getElementById('f-message').value.trim(),
    selling_points: document.getElementById('f-points').value.trim(),
    price: document.getElementById('f-price').value.trim(),
    page_count: selectedPageCount,
  };

  goStep(2);
  await generateCopy();
}

// ===== STEP 2: 멘트 생성 =====
async function generateCopy() {
  const loading = document.getElementById('copy-loading');
  const container = document.getElementById('sections-container');

  loading.style.display = 'block';
  container.style.display = 'none';

  try {
    const res = await apiFetch('/api/generate-copy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookInfo),
    });

    if (!res.ok) throw new Error('API 오류');
    const data = await res.json();

    if (!data.sections || data.sections.length === 0) {
      throw new Error('멘트 생성 실패');
    }

    sections = data.sections;
    renderSections(sections);

    loading.style.display = 'none';
    container.style.display = 'block';

  } catch (err) {
    loading.style.display = 'none';
    showToast('멘트 생성에 실패했어요. 다시 시도해주세요.');
    goStep(1);
  }
}

// ===== 섹션 렌더링 =====
function renderSections(sectionList) {
  const list = document.getElementById('sections-list');
  list.innerHTML = '';

  sectionList.forEach((sec) => {
    const card = document.createElement('div');
    card.className = 'section-card';
    card.innerHTML = `
      <div class="section-header" onclick="toggleSection(this)">
        <div class="section-meta">
          <div class="section-num">${sec.id}</div>
          <div class="section-title-label">${sec.title}</div>
        </div>
        <span class="section-toggle">▼</span>
      </div>
      <div class="section-body">
        <textarea class="section-textarea" data-id="${sec.id}" rows="4">${sec.content}</textarea>
      </div>
    `;
    list.appendChild(card);
  });
}

function toggleSection(header) {
  const card = header.parentElement;
  card.classList.toggle('open');
}

// 섹션 내용 수집 (편집된 값 반영)
function collectSections() {
  return sections.map((sec) => {
    const textarea = document.querySelector(`.section-textarea[data-id="${sec.id}"]`);
    return {
      ...sec,
      content: textarea ? textarea.value.trim() : sec.content,
    };
  });
}

// ===== STEP 3: 다중 파일 업로드 처리 =====
function handleFileSelect(input) {
  const newFiles = Array.from(input.files);
  input.value = ''; // 동일 파일 재선택 허용

  for (const file of newFiles) {
    if (!file.type.startsWith('image/')) {
      showToast(`${file.name}: 이미지 파일만 가능해요.`);
      continue;
    }
    if (file.size > 16 * 1024 * 1024) {
      showToast(`${file.name}: 16MB 이하만 가능해요.`);
      continue;
    }
    if (selectedFiles.length >= 10) {
      showToast('최대 10장까지만 올릴 수 있어요.');
      break;
    }
    selectedFiles.push(file);
  }
  renderPreviews();
}

function renderPreviews() {
  const grid = document.getElementById('preview-grid');
  const inner = document.getElementById('upload-inner');
  const notice = document.getElementById('skip-notice');
  grid.innerHTML = '';

  if (selectedFiles.length === 0) {
    inner.style.display = 'flex';
    notice.style.display = 'block';
    return;
  }

  inner.style.display = 'none';
  notice.style.display = 'none';

  selectedFiles.forEach((file, idx) => {
    const item = document.createElement('div');
    item.className = 'preview-item';
    const img = document.createElement('img');
    const reader = new FileReader();
    reader.onload = (e) => { img.src = e.target.result; };
    reader.readAsDataURL(file);
    item.appendChild(img);

    const num = document.createElement('div');
    num.className = 'img-num';
    num.textContent = `${idx + 1}`;
    item.appendChild(num);

    const btn = document.createElement('button');
    btn.className = 'remove-btn';
    btn.textContent = '✕';
    btn.onclick = () => { selectedFiles.splice(idx, 1); renderPreviews(); };
    item.appendChild(btn);
    grid.appendChild(item);
  });

  // 추가 버튼 (10장 미만일 때)
  if (selectedFiles.length < 10) {
    const addBtn = document.createElement('button');
    addBtn.className = 'add-more-btn';
    addBtn.innerHTML = '<span>+</span>추가';
    addBtn.onclick = () => document.getElementById('design-file').click();
    grid.appendChild(addBtn);
  }
}

// 드래그앤드롭 설정
function setupDragDrop() {
  const area = document.getElementById('upload-area');
  if (!area) return;

  area.addEventListener('dragover', (e) => {
    e.preventDefault();
    area.classList.add('drag-over');
  });
  area.addEventListener('dragleave', () => area.classList.remove('drag-over'));
  area.addEventListener('drop', (e) => {
    e.preventDefault();
    area.classList.remove('drag-over');
    const input = document.getElementById('design-file');
    const dt = new DataTransfer();
    Array.from(e.dataTransfer.files).forEach(f => dt.items.add(f));
    input.files = dt.files;
    handleFileSelect(input);
  });
}

// ===== STEP 3→4: 디자인 분석 + 페이지 생성 =====
async function handleDesignAndCreate() {
  const actions = document.getElementById('design-actions');
  const loading = document.getElementById('design-loading');

  goStep(4);
  const pageLoading = document.getElementById('page-loading');
  const resultContainer = document.getElementById('result-container');
  pageLoading.style.display = 'block';
  resultContainer.style.display = 'none';

  // 1) 이미지가 있으면 분석
  if (selectedFiles.length > 0) {
    try {
      const formData = new FormData();
      selectedFiles.forEach(f => formData.append('images', f));

      const res = await apiFetch('/api/analyze-design', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        designAnalysis = data.analysis;
      }
    } catch (err) {
      designAnalysis = null;
    }
  }

  // 2) 페이지 생성
  await createPage();
}

async function createPage() {
  const pageLoading = document.getElementById('page-loading');
  const resultContainer = document.getElementById('result-container');

  const finalSections = collectSections();

  try {
    const res = await apiFetch('/api/create-page', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        book_info: bookInfo,
        sections: finalSections,
        design_analysis: designAnalysis,
      }),
    });

    if (!res.ok) throw new Error('페이지 생성 실패');
    const data = await res.json();

    const fullUrl = window.location.origin + data.url;
    currentPageId = data.page_id;

    document.getElementById('result-title').textContent = bookInfo.title;
    document.getElementById('result-author').textContent = bookInfo.author ? `저자: ${bookInfo.author}` : '';
    document.getElementById('result-link').value = fullUrl;
    document.getElementById('result-open').href = data.url;

    pageLoading.style.display = 'none';
    resultContainer.style.display = 'block';

  } catch (err) {
    pageLoading.style.display = 'none';
    showToast('페이지 생성에 실패했어요. 다시 시도해주세요.');
    goStep(3);
  }
}

// ===== 링크 복사 =====
function copyLink() {
  const input = document.getElementById('result-link');
  input.select();
  navigator.clipboard.writeText(input.value).then(() => {
    showToast('링크가 복사됐어요!');
  }).catch(() => {
    document.execCommand('copy');
    showToast('링크가 복사됐어요!');
  });
}

// ===== 새 페이지 시작 =====
function startNew() {
  bookInfo = {};
  sections = [];
  designAnalysis = null;
  selectedFiles = [];

  document.getElementById('book-form').reset();
  document.getElementById('sections-list').innerHTML = '';
  renderPreviews();

  goStep(1);
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ===== 다운로드 =====
let currentPageId = null;

function downloadPage(fmt) {
  if (!currentPageId) return;
  const notice = document.getElementById('download-notice');
  notice.style.display = 'block';
  notice.textContent = `⏳ ${fmt.toUpperCase()} 변환 중... 잠시만 기다려주세요 (10~20초)`;

  const link = document.createElement('a');
  link.href = `/api/download/${currentPageId}/${fmt}`;
  link.style.display = 'none';
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  setTimeout(() => { notice.style.display = 'none'; }, 25000);
}

// ===== 토스트 =====
function showToast(msg) {
  const toast = document.getElementById('toast');
  toast.textContent = msg;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 3000);
}
