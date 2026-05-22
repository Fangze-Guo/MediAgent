"""
Skill 服务层
负责从 ~/.claude/skills 目录读取真实的 skill 文件
"""

import os
import re
from pathlib import Path
from typing import List, Optional, Dict, Any
import asyncio


class SkillService:
    """Skill 服务类 - 从文件系统读取 skills"""
    
    def __init__(self, skills_dir: str = None):
        """
        初始化服务
        Args:
            skills_dir: skills 目录路径，默认读取 GLOBAL_SKILLS_DIR 环境变量
        """
        if skills_dir is None:
            skills_dir = os.getenv("GLOBAL_SKILLS_DIR", os.path.expanduser("~/.claude/skills"))
        self.skills_dir = Path(skills_dir)

    @classmethod
    def for_project(cls, project_id: str) -> "SkillService":
        """
        根据 project_id 创建对应项目的 SkillService。
        技能目录约定为 <project.base_dir>/.claude/skills/
        """
        from src.server_agent.agent.claude.project_config import get_project_config
        config = get_project_config(project_id)
        if config:
            skills_dir = config.base_dir / ".claude" / "skills"
            return cls(str(skills_dir))
        return cls()
        
    def _parse_skill_md(self, skill_path: Path) -> Optional[Dict[str, Any]]:
        """
        解析 SKILL.md 文件
        Args:
            skill_path: SKILL.md 文件路径
        Returns:
            解析后的 skill 信息字典
        """
        try:
            with open(skill_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 解析 YAML front matter
            yaml_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)$', content, re.DOTALL)
            if not yaml_match:
                return None
            
            yaml_content = yaml_match.group(1)
            markdown_content = yaml_match.group(2).strip()
            
            # 简单解析 YAML（只处理基本的 key: value 格式）
            metadata = {}
            for line in yaml_content.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    metadata[key.strip()] = value.strip()
            
            # 提取第一段作为简短描述
            description = metadata.get('description', '')
            
            # 从 markdown 内容中提取更详细的描述（第一个段落）
            full_description = markdown_content
            paragraphs = markdown_content.split('\n\n')
            if len(paragraphs) > 1:
                # 跳过标题，取第一个实际段落
                for para in paragraphs:
                    if para.strip() and not para.strip().startswith('#'):
                        full_description = para.strip()
                        break
            
            return {
                'metadata': metadata,
                'description': description,
                'full_description': full_description,
                'markdown_content': markdown_content
            }
            
        except Exception as e:
            print(f"解析 SKILL.md 失败: {skill_path}, 错误: {e}")
            return None
    
    async def get_skills(self, type: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取 skill 列表
        Args:
            type: 分类筛选 (可选)
            search: 搜索关键词 (可选)
        Returns:
            skill 列表
        """
        def sync_get_skills():
            skills = []
            
            if not self.skills_dir.exists():
                return skills
            
            # 遍历 skills 目录
            for skill_dir in self.skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue
                
                skill_md_path = skill_dir / "SKILL.md"
                if not skill_md_path.exists():
                    continue
                
                # 解析 SKILL.md
                parsed = self._parse_skill_md(skill_md_path)
                if not parsed:
                    continue
                
                metadata = parsed['metadata']
                skill_name = metadata.get('name', skill_dir.name)
                skill_description = parsed['description']
                
                # 构建 skill 信息
                skill_info = {
                    'id': skill_dir.name,
                    'name': skill_name,
                    'type': metadata.get('type', 'user-invocable'),
                    'description': skill_description,
                    'full_description': parsed['full_description'],
                    'version': metadata.get('version', '1.0.0'),
                    'author': metadata.get('author', 'Claude Skills'),
                    'downloads': 0,
                    'rating': 5.0,
                    'installed': True,  # 本地 skills 都视为已安装
                    'featured': False,
                    'tags': [metadata.get('type', 'user-invocable')],
                    'created_at': ''
                }
                
                skills.append(skill_info)
            
            # 应用筛选
            if type and type != "全部":
                skills = [s for s in skills if s['type'] == type]
            
            if search:
                search_lower = search.lower()
                skills = [s for s in skills if 
                         search_lower in s['name'].lower() or 
                         search_lower in s['description'].lower()]
            
            # 按名称排序
            skills.sort(key=lambda x: x['name'])
            
            return skills

        return await asyncio.to_thread(sync_get_skills)

    async def get_skill_detail(self, skill_id: str) -> Optional[Dict[str, Any]]:
        """
        获取 skill 详情
        Args:
            skill_id: skill ID（目录名）
        Returns:
            skill 详情信息
        """
        def sync_get_detail():
            skill_dir = self.skills_dir / skill_id
            if not skill_dir.exists() or not skill_dir.is_dir():
                return None

            skill_md_path = skill_dir / "SKILL.md"
            if not skill_md_path.exists():
                return None

            parsed = self._parse_skill_md(skill_md_path)
            if not parsed:
                return None

            metadata = parsed['metadata']
            skill_name = metadata.get('name', skill_dir.name)

            return {
                'id': skill_dir.name,
                'name': skill_name,
                'type': metadata.get('type', 'user-invocable'),
                'description': parsed['description'],
                'full_description': parsed['markdown_content'],  # 返回完整的 markdown 内容
                'features': parsed['markdown_content'],  # 功能特点也使用 markdown 内容
                'version': metadata.get('version', '1.0.0'),
                'author': metadata.get('author', 'Claude Skills'),
                'downloads': 0,
                'rating': 5.0,
                'installed': True,
                'featured': False,
                'tags': [metadata.get('type', 'user-invocable')],
                'created_at': ''
            }

        return await asyncio.to_thread(sync_get_detail)

    async def get_types(self) -> List[str]:
        """
        获取所有 skill 类型
        Returns:
            类型列表
        """
        def sync_get_types():
            types = set()

            if not self.skills_dir.exists():
                return ["全部"]

            for skill_dir in self.skills_dir.iterdir():
                if not skill_dir.is_dir():
                    continue

                skill_md_path = skill_dir / "SKILL.md"
                if not skill_md_path.exists():
                    continue

                parsed = self._parse_skill_md(skill_md_path)
                if parsed:
                    metadata = parsed['metadata']
                    skill_type = metadata.get('type', 'user-invocable')
                    types.add(skill_type)

            return ["全部"] + sorted(list(types))

        return await asyncio.to_thread(sync_get_types)

    def _build_file_tree(self, directory: Path, base_path: Path) -> List[Dict[str, Any]]:
        """
        递归构建文件树结构
        Args:
            directory: 当前目录路径
            base_path: skill 根目录路径
        Returns:
            文件树列表
        """
        items = []

        try:
            # 获取目录下的所有项，排序（目录在前，文件在后）
            entries = sorted(directory.iterdir(), key=lambda x: (not x.is_dir(), x.name))

            for entry in entries:
                # 跳过隐藏文件和 __pycache__
                if entry.name.startswith('.') or entry.name == '__pycache__':
                    continue

                # 计算相对路径
                relative_path = str(entry.relative_to(base_path))

                if entry.is_dir():
                    # 递归处理子目录
                    children = self._build_file_tree(entry, base_path)
                    items.append({
                        'name': entry.name,
                        'type': 'directory',
                        'path': relative_path,
                        'children': children
                    })
                else:
                    # 文件项
                    items.append({
                        'name': entry.name,
                        'type': 'file',
                        'path': relative_path,
                        'size': entry.stat().st_size
                    })
        except Exception as e:
            print(f"构建文件树失败: {directory}, 错误: {e}")

        return items

    async def get_skill_files(self, skill_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取 skill 的文件树结构
        Args:
            skill_id: skill ID（目录名）
        Returns:
            文件树列表
        """
        def sync_get_files():
            skill_dir = self.skills_dir / skill_id
            if not skill_dir.exists() or not skill_dir.is_dir():
                return None

            return self._build_file_tree(skill_dir, skill_dir)

        return await asyncio.to_thread(sync_get_files)

    async def get_skill_file_content(self, skill_id: str, file_path: str) -> Optional[Dict[str, Any]]:
        """
        获取 skill 中某个文件的内容
        Args:
            skill_id: skill ID（目录名）
            file_path: 文件相对路径
        Returns:
            文件内容字典 {content, encoding, size}
        """
        def sync_get_content():
            skill_dir = self.skills_dir / skill_id
            if not skill_dir.exists() or not skill_dir.is_dir():
                return None

            # 安全检查：防止路径遍历攻击
            file_full_path = (skill_dir / file_path).resolve()
            if not str(file_full_path).startswith(str(skill_dir.resolve())):
                print(f"安全警告：尝试访问 skill 目录外的文件: {file_path}")
                return None

            if not file_full_path.exists() or not file_full_path.is_file():
                return None

            try:
                # 尝试以文本模式读取
                with open(file_full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    return {
                        'content': content,
                        'encoding': 'utf-8',
                        'size': file_full_path.stat().st_size,
                        'is_binary': False
                    }
            except UnicodeDecodeError:
                # 如果是二进制文件，返回提示信息
                return {
                    'content': '',
                    'encoding': 'binary',
                    'size': file_full_path.stat().st_size,
                    'is_binary': True
                }
            except Exception as e:
                print(f"读取文件失败: {file_full_path}, 错误: {e}")
                return None

        return await asyncio.to_thread(sync_get_content)
