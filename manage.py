#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys
from dotenv import load_dotenv

def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'logistics_site.settings')
    load_dotenv()

    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # ✅ 项目启动时，全量构建知识库（扫描media嵌套文件夹）
    try:
        from training.knowledge_utils import build_full_kb_on_startup
        build_full_kb_on_startup()
    except ImportError as e:
        print(f"⚠️  导入知识库工具失败：{e}，请检查knowledge_utils.py是否在training文件夹下")
    except Exception as e:
        print(f"⚠️  全量知识库构建失败：{e}")

    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()