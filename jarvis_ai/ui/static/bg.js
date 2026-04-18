(function () {
    const SEPARATION = 150;
    const w = window.innerWidth;
    const AMOUNTX = w <= 768 ? 20 : w <= 1079 ? 30 : 40;
    const AMOUNTY = w <= 768 ? 30 : w <= 1079 ? 45 : 60;
    const WAVE_SPEED = 0.07;

    const container = document.getElementById('dotted-surface');
    if (!container || !window.THREE) {
        return;
    }

    if (container.dataset.initialized === 'true') {
        return;
    }
    container.dataset.initialized = 'true';

    let scene;
    let camera;
    let renderer;
    let geometry;
    let frameId = null;
    let count = 0;
    let isAnimating = false;

    function readThemePalette() {
        const styles = window.getComputedStyle(document.documentElement);
        const fogHex = styles.getPropertyValue('--bg-root').trim() || '#0d0f14';
        const dotColor = new THREE.Color('#ffffff');
        const fogColor = new THREE.Color(fogHex);

        return { dotColor, fogColor };
    }

    try {
        const palette = readThemePalette();
        scene = new THREE.Scene();
        scene.fog = new THREE.Fog(palette.fogColor.getHex(), 2000, 10000);

        camera = new THREE.PerspectiveCamera(
            60,
            window.innerWidth / window.innerHeight,
            1,
            10000
        );
        camera.position.set(0, 355, 1220);

        renderer = new THREE.WebGLRenderer({
            alpha: true,
            antialias: true
        });
        renderer.setPixelRatio(window.devicePixelRatio || 1);
        renderer.setSize(window.innerWidth, window.innerHeight);
        renderer.setClearColor(scene.fog.color, 0);
        renderer.domElement.setAttribute('aria-hidden', 'true');
        container.appendChild(renderer.domElement);

        const positions = [];
        const colors = [];

        for (let ix = 0; ix < AMOUNTX; ix++) {
            for (let iy = 0; iy < AMOUNTY; iy++) {
                positions.push(
                    ix * SEPARATION - (AMOUNTX * SEPARATION) / 2,
                    0,
                    iy * SEPARATION - (AMOUNTY * SEPARATION) / 2
                );
                colors.push(
                    palette.dotColor.r,
                    palette.dotColor.g,
                    palette.dotColor.b
                );
            }
        }

        geometry = new THREE.BufferGeometry();
        geometry.setAttribute(
            'position',
            new THREE.Float32BufferAttribute(positions, 3)
        );
        geometry.setAttribute(
            'color',
            new THREE.Float32BufferAttribute(colors, 3)
        );

        const material = new THREE.PointsMaterial({
            size: 6,
            vertexColors: true,
            transparent: true,
            opacity: 0.74,
            sizeAttenuation: true
        });

        const points = new THREE.Points(geometry, material);
        scene.add(points);
    } catch (_error) {
        container.textContent = '';
        return;
    }

    function animate() {
        isAnimating = true;
        frameId = window.requestAnimationFrame(animate);

        const positionAttribute = geometry.attributes.position;
        const positionArray = positionAttribute.array;
        let index = 0;

        for (let ix = 0; ix < AMOUNTX; ix++) {
            for (let iy = 0; iy < AMOUNTY; iy++) {
                positionArray[index * 3 + 1] =
                    Math.sin((ix + count) * 0.3) * 50 +
                    Math.sin((iy + count) * 0.5) * 50;
                index++;
            }
        }

        positionAttribute.needsUpdate = true;
        renderer.render(scene, camera);
        count += WAVE_SPEED;
    }

    function handleResize() {
        if (!camera || !renderer) {
            return;
        }
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    }

    function handleUnload() {
        window.removeEventListener('resize', handleResize);
        document.removeEventListener('visibilitychange', handleVisibilityChange);
        window.removeEventListener('beforeunload', handleUnload);
        if (frameId !== null) {
            window.cancelAnimationFrame(frameId);
        }
        isAnimating = false;
        if (geometry) {
            geometry.dispose();
        }
        if (renderer) {
            renderer.dispose();
            if (container.contains(renderer.domElement)) {
                container.removeChild(renderer.domElement);
            }
        }
    }

    function handleVisibilityChange() {
        if (document.hidden) {
            if (frameId !== null) {
                window.cancelAnimationFrame(frameId);
                frameId = null;
            }
            isAnimating = false;
            return;
        }
        if (!isAnimating) {
            animate();
        }
    }

    window.addEventListener('resize', handleResize);
    document.addEventListener('visibilitychange', handleVisibilityChange);
    window.addEventListener('beforeunload', handleUnload);
    animate();
})();
