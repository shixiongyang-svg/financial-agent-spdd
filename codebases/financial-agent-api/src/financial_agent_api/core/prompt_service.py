"""Centralized Jinja2-based prompt template service.

Rationale (见 Task 4 决议 4):
- StrictUndefined 硬编码而非环境变量：缺变量应当直接失败，不应运行时开关
- 模板路径硬编码为源码常量：提示与代码结构强绑定，不需环境解耦
- 所有模板版本化存储在 src/financial_agent_api/core/prompts/ 便于回归测试
"""
from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, UndefinedError


class PromptService:
    """Single source of truth for all prompt templates."""

    # 硬编码的模板路径（相对于本文件所在目录）
    _TEMPLATES_DIR = Path(__file__).parent / "prompts"

    # 模板列表（用于启动时校验）
    _REQUIRED_TEMPLATES = [
        "scenario_extraction.j2",
        "compress_history.j2",
        "summarization.j2",
        "synthesise.j2",
    ]
    _OPTIONAL_TEMPLATES = [
        "feedback_prompt.j2",
    ]

    def __init__(self):
        """初始化 Jinja2 环境，启用 StrictUndefined。"""
        # StrictUndefined: 缺失变量直接抛 UndefinedError，不返回空字符串
        self.env = Environment(
            loader=FileSystemLoader(str(self._TEMPLATES_DIR)),
            undefined=StrictUndefined,
        )

    def render(self, template_name: str, **context) -> str:
        """渲染指定模板。

        Args:
            template_name: 模板文件名（如 "scenario_extraction.j2"）
            **context: 模板变量字典

        Returns:
            渲染后的文本

        Raises:
            TemplateNotFound: 模板文件不存在
            UndefinedError: 缺失必填变量（StrictUndefined 生效）
        """
        try:
            template = self.env.get_template(template_name)
            return template.render(**context)
        except UndefinedError as e:
            raise UndefinedError(
                f"缺失必填变量在模板 {template_name}: {str(e)}"
            ) from e
        except TemplateNotFound as e:
            raise TemplateNotFound(
                f"模板文件不存在: {template_name} (期望位置: {self._TEMPLATES_DIR / template_name})"
            ) from e

    def verify_templates(self) -> dict[str, bool]:
        """编译期校验：检查所有必须的模板是否存在且可加载。

        Returns:
            字典，key 为模板名，value 为是否存在/可加载
        """
        results = {}

        for template_name in self._REQUIRED_TEMPLATES:
            try:
                self.env.get_template(template_name)
                results[template_name] = True
            except TemplateNotFound:
                results[template_name] = False

        for template_name in self._OPTIONAL_TEMPLATES:
            try:
                self.env.get_template(template_name)
                results[template_name] = True
            except TemplateNotFound:
                results[template_name] = False

        return results

    def has_template(self, template_name: str) -> bool:
        """检查模板是否存在。"""
        try:
            self.env.get_template(template_name)
            return True
        except TemplateNotFound:
            return False
