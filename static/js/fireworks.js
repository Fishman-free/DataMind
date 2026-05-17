/**
 * fireworks.js — 鼠标点击星星烟花特效
 * 点击任意位置，在点击坐标迸溅出带光晕的星形粒子
 */
(function () {
  'use strict';

  // 粒子形状（Unicode 星号符号）
  const SHAPES = ['✦', '✧', '✸', '✹', '★', '✺', '+', '·'];

  // 配色：与项目主题（电蓝 / 青色 / 紫色 / 白色）一致
  const COLORS = [
    '#4D8AFF', '#00E5FF', '#9B59FF', '#ffffff',
    '#00E5A0', '#A4F4FD', '#7eb8ff', '#c084fc',
  ];

  /**
   * 在 (x, y) 处生成一颗粒子
   * @param {number} x  - 视口 x 坐标
   * @param {number} y  - 视口 y 坐标
   * @param {string} color
   * @param {number} angle  - 飞行角度（弧度）
   * @param {number} speed  - 飞行距离（px）
   * @param {number} delay  - 动画延迟（ms）
   */
  function spawnParticle(x, y, color, angle, speed, delay) {
    const el = document.createElement('span');
    el.className = 'fw-particle';
    el.textContent = SHAPES[Math.floor(Math.random() * SHAPES.length)];

    const size   = 10 + Math.random() * 10;          // 10–20 px
    const tx     = Math.cos(angle) * speed;           // 最终 x 偏移
    const ty     = Math.sin(angle) * speed;           // 最终 y 偏移
    const rotate = (Math.random() - 0.5) * 540;      // 旋转角度
    const dur    = 550 + Math.random() * 300;         // 持续时间 ms

    el.style.cssText = [
      `left:${x}px`,
      `top:${y}px`,
      `font-size:${size}px`,
      `color:${color}`,
      `text-shadow:0 0 8px ${color}, 0 0 16px ${color}`,
      `--fw-tx:${tx}px`,
      `--fw-ty:${ty}px`,
      `--fw-rot:${rotate}deg`,
      `animation-duration:${dur}ms`,
      `animation-delay:${delay}ms`,
    ].join(';');

    document.body.appendChild(el);

    // 动画结束后自动清理 DOM
    el.addEventListener('animationend', () => el.remove(), { once: true });
  }

  /**
   * 点击事件：在点击位置生成一批粒子
   */
  function onBodyClick(e) {
    // 跳过拖拽遮罩层上的点击（避免上传时触发）
    if (e.target.closest('#drag-overlay')) return;

    const x = e.clientX;
    const y = e.clientY;

    // 粒子数量：12-16 颗
    const count = 12 + Math.floor(Math.random() * 5);

    for (let i = 0; i < count; i++) {
      const angle = (Math.PI * 2 * i) / count + (Math.random() - 0.5) * 0.5;
      const speed = 45 + Math.random() * 70;
      const color = COLORS[Math.floor(Math.random() * COLORS.length)];
      const delay = Math.random() * 60;             // 0–60 ms 的随机延迟，避免所有粒子同时爆发
      spawnParticle(x, y, color, angle, speed, delay);
    }

    // 额外：在中心点生成一个快速消散的环形光晕
    spawnRing(x, y);
  }

  /**
   * 点击中心：生成一个快速扩散后消失的圆环光晕
   */
  function spawnRing(x, y) {
    const ring = document.createElement('span');
    ring.className = 'fw-ring';
    ring.style.cssText = `left:${x}px;top:${y}px`;
    document.body.appendChild(ring);
    ring.addEventListener('animationend', () => ring.remove(), { once: true });
  }

  // 注册点击监听（捕获阶段，确保所有元素点击都能触发）
  document.addEventListener('click', onBodyClick, { passive: true });
})();
