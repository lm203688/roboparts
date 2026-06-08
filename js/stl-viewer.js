/* Three.js STL Viewer for RoboLink */

let stlViewer = null;
let stlScene = null;
let stlRenderer = null;
let stlCamera = null;
let stlControls = null;
let stlCurrentModel = null;
let stlAnimId = null;

function initSTLViewer() {
    // 加载Three.js
    if (typeof THREE === 'undefined') {
        const script = document.createElement('script');
        script.src = 'https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js';
        script.onload = () => {
            const script2 = document.createElement('script');
            script2.src = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js';
            script2.onload = () => {
                const script3 = document.createElement('script');
                script3.src = 'https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/loaders/STLLoader.js';
                script3.onload = () => setupViewer();
                script3.onerror = () => setupViewer(); // fallback
                document.head.appendChild(script3);
            };
            document.head.appendChild(script2);
        };
        document.head.appendChild(script);
    } else {
        setupViewer();
    }
}

function setupViewer() {
    stlViewer = document.getElementById('stl3dViewer');
    if (!stlViewer) return;

    const w = stlViewer.clientWidth || 400;
    const h = stlViewer.clientHeight || 300;

    stlScene = new THREE.Scene();
    stlScene.background = new THREE.Color(0xf8f7f4);

    stlCamera = new THREE.PerspectiveCamera(45, w / h, 0.1, 1000);
    stlCamera.position.set(50, 40, 50);

    stlRenderer = new THREE.WebGLRenderer({ antialias: true });
    stlRenderer.setSize(w, h);
    stlRenderer.setPixelRatio(window.devicePixelRatio);
    stlViewer.appendChild(stlRenderer.domElement);

    // Lights
    const ambientLight = new THREE.AmbientLight(0x404040, 1.5);
    stlScene.add(ambientLight);
    const dirLight = new THREE.DirectionalLight(0xffffff, 1.2);
    dirLight.position.set(50, 80, 50);
    stlScene.add(dirLight);
    const dirLight2 = new THREE.DirectionalLight(0x8888ff, 0.4);
    dirLight2.position.set(-50, 20, -50);
    stlScene.add(dirLight2);

    // Grid
    const grid = new THREE.GridHelper(100, 20, 0xcccccc, 0xe8e8e8);
    stlScene.add(grid);

    // Controls
    if (typeof THREE.OrbitControls !== 'undefined') {
        stlControls = new THREE.OrbitControls(stlCamera, stlRenderer.domElement);
        stlControls.enableDamping = true;
        stlControls.dampingFactor = 0.05;
        stlControls.autoRotate = true;
        stlControls.autoRotateSpeed = 2;
    }

    animate();
}

function animate() {
    stlAnimId = requestAnimationFrame(animate);
    if (stlControls) stlControls.update();
    if (stlRenderer) stlRenderer.render(stlScene, stlCamera);
}

function loadSTLModel(id) {
    const url = `stl/${id}.stl`;

    // Remove old model
    if (stlCurrentModel) {
        stlScene.remove(stlCurrentModel);
        stlCurrentModel = null;
    }

    // Show viewer modal
    const modal = document.getElementById('stlPreviewModal');
    if (modal) modal.style.display = 'flex';

    // Init viewer if not yet
    if (!stlRenderer) {
        initSTLViewer();
        setTimeout(() => loadSTLModel(id), 1500);
        return;
    }

    if (typeof THREE.STLLoader === 'undefined') {
        // Fallback: can't load STL, show message
        showToast('3D预览加载中，请稍后刷新重试');
        return;
    }

    const loader = new THREE.STLLoader();
    loader.load(url, (geometry) => {
        const material = new THREE.MeshPhongMaterial({
            color: 0x378ADD,
            specular: 0x333333,
            shininess: 60,
            flatShading: true
        });
        const mesh = new THREE.Mesh(geometry, material);

        // Center and scale
        geometry.computeBoundingBox();
        const bbox = geometry.boundingBox;
        const center = new THREE.Vector3();
        bbox.getCenter(center);
        mesh.position.sub(center);

        const size = new THREE.Vector3();
        bbox.getSize(size);
        const maxDim = Math.max(size.x, size.y, size.z);
        const scale = 60 / maxDim;
        mesh.scale.set(scale, scale, scale);

        stlScene.add(mesh);
        stlCurrentModel = mesh;

        // Reset camera
        stlCamera.position.set(50, 40, 50);
        stlCamera.lookAt(0, 0, 0);
        if (stlControls) {
            stlControls.target.set(0, 0, 0);
            stlControls.update();
        }
    }, undefined, (err) => {
        showToast('模型加载失败');
    });
}

function closeSTLPreview() {
    const modal = document.getElementById('stlPreviewModal');
    if (modal) modal.style.display = 'none';
}
