import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';

const API_BASE = 'http://localhost:5050';

// ─── DOM refs ────────────────────────────────────────────────────────────────
const uploadZone   = document.getElementById('upload-zone');
const fileInput    = document.getElementById('file-input');
const previewImg   = document.getElementById('preview-img');
const btnAnalyze   = document.getElementById('btn-analyze');
const logArea      = document.getElementById('log-area');
const matList      = document.getElementById('materials-list');
const loadingMsg   = document.getElementById('loading-msg');
const graphImg     = document.getElementById('graph-img');
const statusDot    = document.getElementById('status-dot');
const statusLabel  = document.getElementById('status-label');
const tooltip      = document.getElementById('tooltip');

// Stats
const statWalls = document.getElementById('stat-walls');
const statRooms = document.getElementById('stat-rooms');
const statLB    = document.getElementById('stat-lb');
const statPT    = document.getElementById('stat-pt');

// ─── Logging ─────────────────────────────────────────────────────────────────
function log(msg, type = '') {
  const el = document.createElement('div');
  el.className = `log-line ${type}`;
  const ts = new Date().toLocaleTimeString('en', { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' });
  el.textContent = `[${ts}] ${msg}`;
  logArea.appendChild(el);
  logArea.scrollTop = logArea.scrollHeight;
}

// ─── Three.js Setup ───────────────────────────────────────────────────────────
const canvas = document.getElementById('three-canvas');
const viewport = document.getElementById('viewport');

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(window.devicePixelRatio);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.2;

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0c10);
scene.fog = new THREE.Fog(0x0a0c10, 60, 120);

const camera = new THREE.PerspectiveCamera(50, 1, 0.1, 500);
camera.position.set(25, 22, 30);

const controls = new OrbitControls(camera, canvas);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 5;
controls.maxDistance = 100;
controls.maxPolarAngle = Math.PI / 2 + 0.1;

// Lighting
const ambient = new THREE.AmbientLight(0x8aaacc, 0.6);
scene.add(ambient);

const dirLight = new THREE.DirectionalLight(0xffffff, 1.4);
dirLight.position.set(30, 50, 30);
dirLight.castShadow = true;
dirLight.shadow.mapSize.set(2048, 2048);
dirLight.shadow.camera.far = 200;
scene.add(dirLight);

const fillLight = new THREE.DirectionalLight(0x004488, 0.4);
fillLight.position.set(-20, 10, -10);
scene.add(fillLight);

// Grid
const gridHelper = new THREE.GridHelper(80, 40, 0x1e2a38, 0x141920);
gridHelper.position.y = -0.01;
scene.add(gridHelper);

// Materials
const matLB = new THREE.MeshStandardMaterial({ color: 0xff3344, roughness: 0.6, metalness: 0.1 });
const matPT = new THREE.MeshStandardMaterial({ color: 0x00cc66, roughness: 0.7, metalness: 0.05 });
const matFloor = new THREE.MeshStandardMaterial({ color: 0x1a2a3a, roughness: 0.9, metalness: 0.05, transparent: true, opacity: 0.7 });
const matEdge = new THREE.LineBasicMaterial({ color: 0x00d4ff, transparent: true, opacity: 0.15 });

// Resize handler
function resizeRenderer() {
  const w = viewport.clientWidth;
  const h = viewport.clientHeight;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resizeRenderer);
resizeRenderer();

// Render loop
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

// ─── Scene Management ─────────────────────────────────────────────────────────
let buildingGroup = null;

function clearScene() {
  if (buildingGroup) {
    scene.remove(buildingGroup);
    buildingGroup.traverse(obj => {
      if (obj.geometry) obj.geometry.dispose();
    });
    buildingGroup = null;
  }
}

function buildScene(data) {
  clearScene();
  buildingGroup = new THREE.Group();

  const walls3d = data.walls_3d;
  const floor   = data.floor;

  const matWindow = new THREE.MeshStandardMaterial({ color: 0x1e90ff, roughness: 0.4, metalness: 0.2, transparent: true, opacity: 0.6 });

  // Floor slab
  const floorGeo = new THREE.BoxGeometry(floor.width, 0.15, floor.depth);
  const floorMesh = new THREE.Mesh(floorGeo, matFloor);
  floorMesh.position.set(floor.width / 2, -0.075, floor.depth / 2);
  floorMesh.receiveShadow = true;
  buildingGroup.add(floorMesh);

  // Floor edge lines
  const floorEdges = new THREE.EdgesGeometry(floorGeo);
  const floorLines = new THREE.LineSegments(floorEdges, matEdge);
  floorLines.position.copy(floorMesh.position);
  buildingGroup.add(floorLines);

  // Walls
  walls3d.forEach(w => {
    const dx = w.x2 - w.x1;
    const dy = w.y2 - w.y1;
    const len = Math.sqrt(dx * dx + dy * dy);
    if (len < 0.05) return;

    const angle = Math.atan2(dy, dx);
    const mat = w.type === 'load_bearing' ? matLB : matPT;

    const geo = new THREE.BoxGeometry(len, w.height, w.thickness);
    const mesh = new THREE.Mesh(geo, mat);

    mesh.position.set(
      (w.x1 + w.x2) / 2,
      w.height / 2,
      (w.y1 + w.y2) / 2
    );
    mesh.rotation.y = -angle;
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    mesh.userData = { wallType: w.type, length_m: w.length_m };
    buildingGroup.add(mesh);

    // Edge highlight
    const edges = new THREE.EdgesGeometry(geo);
    const lines = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({
      color: w.type === 'load_bearing' ? 0xff6677 : 0x33ff99,
      transparent: true, opacity: 0.25
    }));
    lines.position.copy(mesh.position);
    lines.rotation.copy(mesh.rotation);
    buildingGroup.add(lines);

    // Windows on this wall
    if (w.windows && w.windows.length > 0) {
      w.windows.forEach(win => {
        const dxw = win.x2 - win.x1;
        const dyw = win.y2 - win.y1;
        const lenw = Math.sqrt(dxw * dxw + dyw * dyw);
        if (lenw < 0.05) return;

        const anglew = Math.atan2(dyw, dxw);
        const winGeo = new THREE.BoxGeometry(lenw, 1.2, 0.05);
        const winMesh = new THREE.Mesh(winGeo, matWindow);

        winMesh.position.set(
          (win.x1 + win.x2) / 2,
          1.5,
          (win.y1 + win.y2) / 2
        );
        winMesh.rotation.y = -anglew;
        winMesh.castShadow = true;
        buildingGroup.add(winMesh);
      });
    }
  });

  // Center the building group
  const box = new THREE.Box3().setFromObject(buildingGroup);
  const center = box.getCenter(new THREE.Vector3());
  buildingGroup.position.sub(center);
  buildingGroup.position.y += center.y;

  scene.add(buildingGroup);
  loadingMsg.style.display = 'none';
  log('3D model built — ' + walls3d.length + ' walls, windows integrated', 'ok');
}

// ─── Camera Presets ───────────────────────────────────────────────────────────
function setCameraIsometric() {
  camera.position.set(25, 22, 30);
  controls.target.set(0, 3, 0);
  controls.update();
}
function setCameraTop() {
  camera.position.set(0, 50, 0.1);
  controls.target.set(0, 0, 0);
  controls.update();
}
function setCameraFront() {
  camera.position.set(0, 8, 40);
  controls.target.set(0, 4, 0);
  controls.update();
}

document.getElementById('view-iso').addEventListener('click', setCameraIsometric);
document.getElementById('view-top').addEventListener('click', setCameraTop);
document.getElementById('view-front').addEventListener('click', setCameraFront);
document.getElementById('view-reset').addEventListener('click', () => { setCameraIsometric(); });

// ─── Material Panel ───────────────────────────────────────────────────────────
function renderMaterials(matData) {
  const recs = matData.wall_recommendations;
  const summary = matData.summary;

  let html = '';

  // Summary bar
  html += `<div style="padding:10px 12px 0;font-size:11px;color:var(--text3);font-family:var(--font-mono)">
    PRIMARY STRUCTURAL: <span style="color:var(--yellow)">${summary.primary_structural_material}</span>
    &nbsp;|&nbsp; PARTITION: <span style="color:var(--accent)">${summary.primary_partition_material}</span>
  </div>`;

  recs.forEach((rec, idx) => {
    const typeClass = rec.wall_type;
    const typeLabel = rec.wall_type === 'load_bearing' ? 'LB' : 'PT';
    const top2 = rec.recommendations.slice(0, 2);

    html += `<div class="mat-card" data-idx="${idx}">
      <div class="mat-card-header">
        <span class="mat-type-badge ${typeClass}">${typeLabel}</span>
        <span style="font-size:11px;color:var(--text);font-weight:600">Wall ${idx + 1}</span>
        <span class="mat-len">${rec.length_m}m</span>
      </div>
      <div class="mat-recs">`;

    top2.forEach((m, ri) => {
      const pct = Math.round(m.score * 100);
      html += `<div class="mat-rec-row">
        <div class="mat-rank ${ri === 0 ? 'rank1' : ''}">${ri + 1}</div>
        <div class="mat-name">${m.material}</div>
        <div class="mat-score-bar-wrap"><div class="mat-score-bar" style="width:${pct}%"></div></div>
        <div class="mat-score-val">${pct}%</div>
      </div>`;
    });

    // Format explanation with bold for **text**
    const expl = rec.explanation.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html += `</div><div class="mat-explain">${expl}</div></div>`;
  });

  matList.innerHTML = html;

  // Toggle expand on click
  matList.querySelectorAll('.mat-card').forEach(card => {
    card.addEventListener('click', () => {
      const wasSelected = card.classList.contains('selected');
      matList.querySelectorAll('.mat-card').forEach(c => c.classList.remove('selected'));
      if (!wasSelected) card.classList.add('selected');
    });
  });
}

// ─── File Upload ──────────────────────────────────────────────────────────────
uploadZone.addEventListener('click', () => fileInput.click());
uploadZone.addEventListener('dragover', e => { e.preventDefault(); uploadZone.classList.add('drag-over'); });
uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
uploadZone.addEventListener('drop', e => {
  e.preventDefault();
  uploadZone.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});
fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

let selectedFile = null;

function handleFileSelect(file) {
  selectedFile = file;
  const reader = new FileReader();
  reader.onload = e => {
    previewImg.src = e.target.result;
    previewImg.style.display = 'block';
  };
  reader.readAsDataURL(file);
  btnAnalyze.disabled = false;
  log(`File selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`, 'info');
}

// ─── Analysis ────────────────────────────────────────────────────────────────
async function runAnalysis() {
  if (!selectedFile) {
    log('Please select a floor plan image first.', 'err');
    return;
  }

  btnAnalyze.disabled = true;
  loadingMsg.textContent = 'PROCESSING...';
  loadingMsg.style.display = 'block';
  statusDot.classList.remove('active');
  statusLabel.textContent = 'ANALYZING';

  log('Uploading image for analysis...', 'info');

  try {
    const formData = new FormData();
    formData.append('image', selectedFile);
    log('POST /analyze', 'dim');
    const res = await fetch(`${API_BASE}/analyze`, { method: 'POST', body: formData });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const meta = data.meta;
    log(`Source: ${meta.source.toUpperCase()}`, 'dim');
    log(`Detected ${meta.wall_count} walls, ${meta.room_count} rooms`, 'ok');

    // Update stats
    statWalls.textContent = meta.wall_count;
    statRooms.textContent = meta.room_count;
    statLB.textContent = data.materials.summary.load_bearing_count;
    statPT.textContent = data.materials.summary.partition_count;

    // Build 3D
    log('Generating 3D model...', 'dim');
    buildScene(data);

    // Material panel
    log('Computing material recommendations...', 'dim');
    renderMaterials(data.materials);

    statusDot.classList.add('active');
    statusLabel.textContent = 'COMPLETE';
    log('Pipeline complete ✓', 'ok');

    if (graphImg) {
      graphImg.src = `${API_BASE}/graph?ts=${Date.now()}`;
    }

  } catch (err) {
    log(`Error: ${err.message}`, 'err');
    log('Is the backend running? (python app.py)', 'err');
    loadingMsg.textContent = 'ERROR — CHECK LOG';
    statusLabel.textContent = 'ERROR';
  } finally {
    btnAnalyze.disabled = !selectedFile;
  }
}

btnAnalyze.addEventListener('click', () => runAnalysis());

// ─── Health check ─────────────────────────────────────────────────────────────
async function checkHealth() {
  try {
    const res = await fetch(`${API_BASE}/health`, { signal: AbortSignal.timeout(2000) });
    if (res.ok) {
      statusDot.classList.add('active');
      statusLabel.textContent = 'ONLINE';
      log('Backend connected ✓', 'ok');
    }
  } catch {
    log('Backend not reachable — start with: python app.py', 'err');
  }
}

// Init
log('ASIS initialized', 'info');
log('Stack: OpenCV · Shapely · Flask · Three.js', 'dim');
checkHealth();
