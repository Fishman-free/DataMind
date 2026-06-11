"""
预处理可视化模块。

使用 matplotlib + seaborn 生成 5 张诊断图的 base64 PNG，
用于前端仪表盘展示数据预处理效果。

来源：学生+AI
"""
from __future__ import annotations
import base64, io, json, os, threading, time
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
import matplotlib.patches as mpatches
import numpy as np
import pandas as pd
import seaborn as sns


# ── 中文字体初始化 ────────────────────────────────────────────
# 清除过期缓存 + 显式注册中文字体，确保 macOS / Windows / Linux / Docker 全平台可用

def _build_cn_font() -> fm.FontProperties:
    """
    重建字体缓存并返回一个可用的中文字体 FontProperties。

    策略：
    1. 删除超过 30 天或缺少中文字体条目的 matplotlib 字体缓存
    2. 强制 matplotlib 重建字体列表
    3. 按优先级搜索可用的 CJK 字体
    4. 设置 rcParams 并返回 FontProperties 供所有文本元素使用
    """
    # 1. 按需清除过期缓存
    cache_dir = matplotlib.get_cachedir()
    try:
        cache_files = [f for f in os.listdir(cache_dir)
                       if f.startswith('fontlist-v') and f.endswith('.json')]
    except FileNotFoundError:
        cache_files = []

    need_rebuild = False
    if cache_files:
        cache_path = os.path.join(cache_dir, cache_files[0])
        cache_age = time.time() - os.path.getmtime(cache_path)
        # 超过 30 天，或缓存文件过小（可能损坏）
        if cache_age > 30 * 86400 or os.path.getsize(cache_path) < 1000:
            need_rebuild = True
        else:
            # 检查缓存中是否包含中文字体条目
            try:
                with open(cache_path, 'rb') as fh:
                    data = json.load(fh)
                has_cjk = any(
                    kw in font.get('name', '')
                    for font in data.get('ttflist', [])
                    for kw in ['YaHei', 'SimHei', 'SimSun', 'KaiTi', 'FangSong']
                )
                if not has_cjk:
                    need_rebuild = True
            except (json.JSONDecodeError, KeyError):
                need_rebuild = True

    if need_rebuild:
        for fn in cache_files:
            try:
                os.remove(os.path.join(cache_dir, fn))
            except OSError:
                pass
        # 触发字体管理器重建
        fm._load_fontmanager(try_read_cache=False)

    # 2. 按优先级搜索可用的中文字体
    cjk_candidates = [
        'Microsoft YaHei',   # Windows（最常用）
        'SimHei',             # Windows（黑体）
        'SimSun',             # Windows（宋体）
        'KaiTi',              # Windows（楷体）
        'FangSong',           # Windows（仿宋）
        'PingFang SC',        # macOS
        'Heiti SC',           # macOS
        'STHeiti',            # macOS
        'Noto Sans CJK SC',   # Linux / Docker
        'WenQuanYi Micro Hei',# Linux
        'WenQuanYi Zen Hei',  # Linux
        'Noto Sans SC',       # Linux
    ]

    cn_name = 'DejaVu Sans'  # 最终兜底（无中文 glyphs）
    for name in cjk_candidates:
        for f in fm.fontManager.ttflist:
            if f.name == name:
                cn_name = name
                break
        if cn_name == name:
            break

    # 3. 设置全局 rcParams
    plt.rcParams['font.sans-serif'] = [cn_name] + [
        n for n in cjk_candidates if n != cn_name
    ] + ['DejaVu Sans']
    plt.rcParams['font.family'] = 'sans-serif'
    plt.rcParams['axes.unicode_minus'] = False

    # 4. 返回 FontProperties 供显式使用
    return fm.FontProperties(family=cn_name)


_CN_FONT = None
_CN_FONT_LOCK = threading.Lock()

def _get_cn_font():
    global _CN_FONT
    if _CN_FONT is None:
        with _CN_FONT_LOCK:
            if _CN_FONT is None:
                _CN_FONT = _build_cn_font()
    return _CN_FONT

# ── 赛博朋克配色常量 ──────────────────────────────────────────

_BG = '#0d1117'
_GRID = '#1e3a5f'
_TXT = '#c9d1d9'
_A  = '#4F9FFF'
_W   = '#FF6B6B'
_OK  = '#00D4AA'


class PreprocessVisualizer:
    # 预处理诊断可视化，生成 5 张图（base64 PNG）。来源：学生+AI

    def __init__(self, df_raw, df_clean, pp_report):
        self._raw = df_raw
        self._clean = df_clean
        self._report = pp_report

    def generate_all(self):
        charts = []
        for fn in [self._chart_missing_heatmap, self._chart_pipeline_funnel,
                   self._chart_outlier_boxplot, self._chart_dtype_pie,
                   self._chart_fill_compare]:
            try:
                charts.append(fn())
            except Exception as exc:
                charts.append({'title': fn.__name__, 'img': '', 'desc': 'error: ' + str(exc)})
        return {'charts': charts}

    def _b64(self, fig):
        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=110, bbox_inches='tight', facecolor=fig.get_facecolor())
        buf.seek(0)
        return 'data:image/png;base64,' + base64.b64encode(buf.read()).decode()

    def _chart_missing_heatmap(self):
        df = self._raw.sample(min(300, len(self._raw)), random_state=42) if len(self._raw) > 300 else self._raw.copy()
        fig, ax = plt.subplots(figsize=(10, 5))
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        mm = df.isnull()
        cmap = ['#1e3a5f', _W] if mm.values.any() else [_OK, _OK]
        data = mm if mm.values.any() else pd.DataFrame(False, index=df.index, columns=df.columns)
        sns.heatmap(data, ax=ax, cbar=False, cmap=cmap, xticklabels=True, yticklabels=False)
        ax.set_title('原始数据缺失值分布热力图', color=_TXT, fontsize=13, pad=10, fontproperties=_get_cn_font())
        ax.set_xlabel('列名', color=_TXT, fontproperties=_get_cn_font())
        ax.set_ylabel('样本行（采样）', color=_TXT, fontproperties=_get_cn_font())
        ax.tick_params(colors=_TXT, labelsize=8)
        plt.xticks(rotation=30, ha='right')
        # 为 seaborn heatmap 的 xticklabels 显式设置字体
        for label in ax.get_xticklabels():
            label.set_fontproperties(_get_cn_font())
        ax.legend(handles=[mpatches.Patch(color='#1e3a5f', label='有值'),
                            mpatches.Patch(color=_W, label='缺失')],
                  loc='upper right', facecolor=_BG, labelcolor=_TXT,
                  prop=_get_cn_font(), fontsize=8)
        plt.tight_layout()
        img = self._b64(fig)
        plt.close(fig)
        return {'title': '缺失值分布热力图', 'img': img,
                'desc': '原始数据共 ' + str(int(self._raw.isnull().sum().sum())) + ' 个缺失单元格，红色表示缺失位置'}

    def _chart_pipeline_funnel(self):
        dup = self._report.get('remove_duplicates') or {}
        inv = self._report.get('filter_invalid_records') or {}
        dr = int(dup.get('removed', 0))
        ir = int(inv.get('removed', 0))
        rf = len(self._clean)
        rm = rf + ir
        ro = rm + dr
        stages = ['原始数据', '去重后', '过滤无效行后']
        rows = [ro, rm, rf]
        fig, ax = plt.subplots(figsize=(8, 3.5))
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        bars = ax.barh(stages, rows, color=[_A, '#9B8EA8', _OK], height=0.5, edgecolor='none')
        for bar, val in zip(bars, rows):
            ax.text(bar.get_width() + max(rows)*0.01, bar.get_y()+bar.get_height()/2,
                    str(val) + ' 行', va='center', ha='left', color=_TXT, fontsize=10,
                    fontproperties=_get_cn_font())
        ax.set_title('预处理流水线行数变化', color=_TXT, fontsize=13, pad=10, fontproperties=_get_cn_font())
        ax.set_xlabel('行数', color=_TXT, fontproperties=_get_cn_font())
        ax.set_ylabel('处理阶段', color=_TXT, fontproperties=_get_cn_font())
        ax.tick_params(colors=_TXT)
        # 为 Y 轴刻度标签显式设置中文字体
        for label in ax.get_yticklabels():
            label.set_fontproperties(_get_cn_font())
        ax.spines[:].set_color(_GRID)
        ax.set_xlim(0, max(rows)*1.18)
        ax.xaxis.grid(True, color=_GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        plt.tight_layout()
        img = self._b64(fig)
        plt.close(fig)
        return {'title': '预处理流水线行数变化', 'img': img,
                'desc': '共删除 ' + str(dr+ir) + ' 行（去重 ' + str(dr) + ' + 无效过滤 ' + str(ir) + '）'}

    def _chart_outlier_boxplot(self):
        nc = [c for c in self._clean.select_dtypes(include='number').columns
              if not c.endswith(('_is_outlier', '_is_extreme_outlier'))][:6]
        fsize = (max(6, len(nc)*1.8) if nc else 6, 5 if nc else 3)
        fig, ax = plt.subplots(figsize=fsize)
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        if nc:
            sns.boxplot(data=self._clean[nc], ax=ax, palette=[_A]*len(nc),
                        flierprops={'marker': 'o', 'markerfacecolor': _W, 'markersize': 4, 'alpha': 0.6},
                        width=0.5)
            ax.set_title('数值列异常值箱线图（IQR x1.5）', color=_TXT, fontsize=13, pad=10, fontproperties=_get_cn_font())
            ax.set_xlabel('列名', color=_TXT, fontproperties=_get_cn_font())
            ax.set_ylabel('数值', color=_TXT, fontproperties=_get_cn_font())
            ax.tick_params(colors=_TXT, labelsize=9)
            ax.spines[:].set_color(_GRID)
            ax.yaxis.grid(True, color=_GRID, linewidth=0.5)
            ax.set_axisbelow(True)
            plt.xticks(rotation=20, ha='right')
            # 为 X 轴刻度标签显式设置中文字体
            for label in ax.get_xticklabels():
                label.set_fontproperties(_get_cn_font())
        else:
            ax.text(0.5, 0.5, '无数值列', transform=ax.transAxes,
                    ha='center', va='center', color=_TXT, fontproperties=_get_cn_font())
            ax.set_title('数值列异常值箱线图', color=_TXT, fontsize=13, fontproperties=_get_cn_font())
        plt.tight_layout()
        img = self._b64(fig)
        plt.close(fig)
        od = (self._report.get('filter_outliers') or {}).get('detail', {})
        desc = '红点为异常值（IQR x1.5），共检测到 ' + str(sum(od.values())) + ' 个异常点' if nc else '无数值列'
        return {'title': '数值列异常值箱线图', 'img': img, 'desc': desc}

    def _chart_dtype_pie(self):
        dc = {}
        for d in self._clean.dtypes:
            k = str(d)
            if 'int' in k:        lbl = '整数 (int)'
            elif 'float' in k:    lbl = '浮点数 (float)'
            elif 'datetime' in k: lbl = '日期时间 (datetime)'
            elif 'category' in k: lbl = '分类 (category)'
            elif 'bool' in k:     lbl = '布尔 (bool)'
            else:                  lbl = '文本 (object)'
            dc[lbl] = dc.get(lbl, 0) + 1
        lb = list(dc.keys())
        sz = list(dc.values())
        pal = [_A, '#9B8EA8', _OK, '#FFB347', _W, '#C4B7A6']
        clr = pal[:len(lb)]
        fig, ax = plt.subplots(figsize=(7, 5))
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        wedges, _, ats = ax.pie(sz, labels=None, colors=clr, autopct='%1.1f%%',
                                 startangle=140, pctdistance=0.78,
                                 wedgeprops={'edgecolor': _BG, 'linewidth': 2})
        for a in ats:
            a.set_color(_BG)
            a.set_fontsize(9)
            a.set_fontweight('bold')
        ax.legend(wedges, [l + '（' + str(s) + ' 列）' for l, s in zip(lb, sz)],
                  loc='lower center', bbox_to_anchor=(0.5, -0.15), ncol=2,
                  facecolor=_BG, labelcolor=_TXT, prop=_get_cn_font(), fontsize=9)
        ax.set_title('列数据类型分布', color=_TXT, fontsize=13, pad=10, fontproperties=_get_cn_font())
        plt.tight_layout()
        img = self._b64(fig)
        plt.close(fig)
        conv = (self._report.get('convert_types') or {}).get('converted', {})
        cv = ', '.join(conv.values()) if conv else '无'
        return {'title': '列数据类型分布', 'img': img,
                'desc': '预处理共转换 ' + str(len(conv)) + ' 列类型（' + cv + '）'}

    def _chart_fill_compare(self):
        mi = (self._report.get('handle_missing') or {}).get('filled_cols', {})
        fsize = (6, 3) if not mi else (max(6, len(mi)*1.5), 5)
        fig, ax = plt.subplots(figsize=fsize)
        fig.patch.set_facecolor(_BG)
        ax.set_facecolor(_BG)
        if not mi:
            ax.text(0.5, 0.5, '无缺失值需填充', transform=ax.transAxes,
                    ha='center', va='center', color=_OK, fontsize=14, fontproperties=_get_cn_font())
            ax.set_title('缺失值填充前后对比', color=_TXT, fontsize=13, fontproperties=_get_cn_font())
            ax.axis('off')
            plt.tight_layout()
            img = self._b64(fig)
            plt.close(fig)
            return {'title': '缺失值填充前后对比', 'img': img, 'desc': '数据集无缺失值，无需填充'}
        cols = list(mi.keys())
        before = [int(v) for v in mi.values()]
        # 从清洗后数据获取实际缺失值数量（填充后应为 0）
        after = [int(self._clean[col].isnull().sum()) if col in self._clean.columns else 0 for col in cols]
        x = np.arange(len(cols))
        w = 0.35
        b1 = ax.bar(x - w/2, before, w, label='填充前', color=_W, alpha=0.85)
        b2 = ax.bar(x + w/2, after, w, label='填充后', color=_OK, alpha=0.85)
        # 为填充前柱子添加数值标签
        for bar in b1:
            h = bar.get_height()
            if h > 0:
                ax.text(bar.get_x()+bar.get_width()/2, h+max(before)*0.02, str(int(h)),
                        ha='center', va='bottom', color=_TXT, fontsize=9, fontproperties=_get_cn_font())
        # 为填充后柱子添加数值标签（包括 0，防止因高度为 0 不可见）
        for bar in b2:
            h = bar.get_height()
            y_offset = max(before)*0.02 if h > 0 else max(max(before)*0.06, 0.5)
            ax.text(bar.get_x()+bar.get_width()/2, y_offset, str(int(h)),
                    ha='center', va='bottom', color=_OK, fontsize=9, fontproperties=_get_cn_font())
        ax.set_title('缺失值填充前后对比', color=_TXT, fontsize=13, pad=10, fontproperties=_get_cn_font())
        ax.set_xlabel('列名', color=_TXT, fontproperties=_get_cn_font())
        ax.set_ylabel('缺失单元格数', color=_TXT, fontproperties=_get_cn_font())
        ax.set_xticks(x)
        ax.set_xticklabels(cols, rotation=20, ha='right', color=_TXT, fontsize=9)
        # 显式为每个 X 轴刻度标签设置中文字体
        for label in ax.get_xticklabels():
            label.set_fontproperties(_get_cn_font())
        ax.tick_params(colors=_TXT)
        ax.spines[:].set_color(_GRID)
        ax.yaxis.grid(True, color=_GRID, linewidth=0.5)
        ax.set_axisbelow(True)
        # 确保 y 轴有足够空间显示标签
        y_max = max(before) * 1.18 if before else 10
        ax.set_ylim(0, y_max)
        ax.legend(facecolor=_BG, labelcolor=_TXT, prop=_get_cn_font(), fontsize=9)
        plt.tight_layout()
        img = self._b64(fig)
        plt.close(fig)
        return {'title': '缺失值填充前后对比', 'img': img,
                'desc': '共填充 ' + str(sum(before)) + ' 个缺失单元格（数值列→均值/中位数，文本列→众数/Unknown）'}
