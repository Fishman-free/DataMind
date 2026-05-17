/**
 * DataMind 空间粒子场 — bg-effects.js
 * Cinematic Space aesthetic: floating star-dust particles with glowing halos
 * 来源：学生+AI
 */
(function () {
    'use strict';

    const canvas = document.getElementById('particle-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const PARTICLE_COUNT = 80;
    const particles = [];

    // ── Resize handler ──────────────────────────────────────────
    function resize() {
        canvas.width  = window.innerWidth;
        canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize, { passive: true });

    // ── Colour palette — electric blue / cyan / purple ──────────
    const COLORS = [
        [77,  138, 255],   // electric blue
        [0,   229, 255],   // vivid cyan
        [155, 89,  255],   // space purple
        [0,   229, 160],   // emerald
        [120, 170, 255],   // soft blue
    ];

    // ── Particle factory ────────────────────────────────────────
    function createParticle(scatter) {
        const c = COLORS[Math.floor(Math.random() * COLORS.length)];
        return {
            x:          scatter ? Math.random() * canvas.width  : Math.random() * canvas.width,
            y:          scatter ? Math.random() * canvas.height : canvas.height + 12,
            vx:         (Math.random() - 0.5) * 0.30,
            vy:         -(Math.random() * 0.38 + 0.08),
            radius:     Math.random() * 1.8 + 0.6,
            alpha:      Math.random() * 0.45 + 0.12,
            alphaDir:   Math.random() > 0.5 ? 1 : -1,
            alphaSpeed: Math.random() * 0.003 + 0.0008,
            color:      c,
        };
    }

    for (let i = 0; i < PARTICLE_COUNT; i++) {
        particles.push(createParticle(true));
    }

    // ── Animation loop ──────────────────────────────────────────
    let rafId = null;

    function draw() {
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];

            // Move
            p.x += p.vx;
            p.y += p.vy;

            // Pulse alpha
            p.alpha += p.alphaSpeed * p.alphaDir;
            if (p.alpha >= 0.60 || p.alpha <= 0.04) p.alphaDir *= -1;

            // Respawn off-screen particles
            if (p.y < -12 || p.x < -12 || p.x > canvas.width + 12) {
                particles[i] = createParticle(false);
                continue;
            }

            const [r, g, b] = p.color;

            // Outer glow halo
            const haloR = p.radius * 4;
            const grad  = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, haloR);
            grad.addColorStop(0,   `rgba(${r},${g},${b},${p.alpha * 0.55})`);
            grad.addColorStop(0.4, `rgba(${r},${g},${b},${p.alpha * 0.18})`);
            grad.addColorStop(1,   `rgba(${r},${g},${b},0)`);
            ctx.beginPath();
            ctx.arc(p.x, p.y, haloR, 0, Math.PI * 2);
            ctx.fillStyle = grad;
            ctx.fill();

            // Core dot
            ctx.beginPath();
            ctx.arc(p.x, p.y, p.radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r},${g},${b},${Math.min(p.alpha * 2.2, 0.95)})`;
            ctx.fill();
        }

        rafId = requestAnimationFrame(draw);
    }

    // Start after initial paint to avoid jank
    setTimeout(function () { draw(); }, 350);

    // Clean up if page is hidden to save GPU
    document.addEventListener('visibilitychange', function () {
        if (document.hidden) {
            cancelAnimationFrame(rafId);
        } else {
            draw();
        }
    });
})();
