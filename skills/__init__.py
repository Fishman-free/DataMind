"""
运行时确定性技能注册表。

每个技能 = 一个子目录（SKILL.md + <name>_skill.py）。SkillRouter 注入所有
SKILL.md，由 LLM 选择技能并生成 JSON 计划，本地脚本确定性执行；未命中时
由 /chat 降级到代码生成兜底。

来源：学生+AI
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from skills._contract import SkillResult
from skills.stats_skill.stats_skill import execute_stats_plan
from skills.viz_skill.viz_skill import execute_viz_plan
from skills.trend_skill.trend_skill import execute_trend_plan
from skills.correlation_skill.correlation_skill import execute_correlation_plan
from skills.distribution_skill.distribution_skill import execute_distribution_plan
from skills.profile_skill.profile_skill import execute_profile_plan

_ROOT = Path(__file__).parent


@dataclass(frozen=True)
class SkillSpec:
    name: str
    title: str
    path: Path
    execute: Callable[..., SkillResult]


SKILLS: dict[str, SkillSpec] = {
    "stats-skill": SkillSpec("stats-skill", "统计分析",
                             _ROOT / "stats_skill" / "SKILL.md", execute_stats_plan),
    "viz-skill": SkillSpec("viz-skill", "数据可视化",
                           _ROOT / "viz_skill" / "SKILL.md", execute_viz_plan),
    "trend-skill": SkillSpec("trend-skill", "趋势分析",
                             _ROOT / "trend_skill" / "SKILL.md", execute_trend_plan),
    "correlation-skill": SkillSpec("correlation-skill", "相关性分析",
                                   _ROOT / "correlation_skill" / "SKILL.md", execute_correlation_plan),
    "distribution-skill": SkillSpec("distribution-skill", "分布分析",
                                    _ROOT / "distribution_skill" / "SKILL.md", execute_distribution_plan),
    "profile-skill": SkillSpec("profile-skill", "数据画像",
                               _ROOT / "profile_skill" / "SKILL.md", execute_profile_plan),
}


def load_catalog() -> str:
    """拼接所有 SKILL.md，注入路由 system prompt。"""
    docs = [f"## {spec.name}\n\n{spec.path.read_text(encoding='utf-8')}"
            for spec in SKILLS.values()]
    return "\n\n---\n\n".join(docs)
