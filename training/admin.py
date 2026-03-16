from django.contrib import admin
from django.utils.html import format_html
from .models import (
    CourseCategory, Course, CourseChapter,
    CourseResource, LearningRecord, Employee
)

# ===================== 自定义Admin类（适配模型实际字段）=====================
class CourseResourceAdmin(admin.ModelAdmin):
    """课程资源Admin（百问百答文件上传）"""
    list_display = ["name", "course", "file_type", "file_size", "upload_time", "file_link"]
    search_fields = ["name", "course__name"]
    list_filter = ["file_type", "course__category"]
    fieldsets = (
        (None, {
            "fields": ("course", "name", "file_type", "file_path"),
            "description": format_html("""
                <strong>百问百答文件上传说明：</strong><br>
                1. 课程需选择「百问百答」分类下的课程；<br>
                2. 支持格式：xlsx（Excel）、docx（Word）、pdf；<br>
                3. Excel需按「工作表=分类，列=问题/答案」格式；<br>
                4. Word需按「标题1=分类，段落=问题：XXX/答案：XXX」格式；<br>
                5. PDF需按「段落=问题：XXX/答案：XXX」格式。
            """)
        }),
    )

    # 自定义显示：文件下载链接
    def file_link(self, obj):
        if obj.file_path:
            return format_html('<a href="{}" target="_blank">查看文件</a>', obj.file_path.url)
        return "无文件"
    file_link.short_description = "文件操作"

    # 自定义显示：文件大小（MB）
    def file_size(self, obj):
        if obj.file_path and hasattr(obj.file_path, 'size'):
            return f"{round(obj.file_path.size / 1024 / 1024, 2)} MB"
        return "0 MB"
    file_size.short_description = "文件大小"

class CourseCategoryAdmin(admin.ModelAdmin):
    """课程分类Admin"""
    list_display = ["name", "sort", "create_time"]
    search_fields = ["name"]
    list_editable = ["sort"]  # 列表页可直接编辑排序

class CourseAdmin(admin.ModelAdmin):
    """课程Admin"""
    list_display = ["name", "category", "difficulty", "create_time"]
    search_fields = ["name"]
    list_filter = ["category", "difficulty"]

class CourseChapterAdmin(admin.ModelAdmin):
    """课程章节Admin"""
    list_display = ["name", "course", "chapter_type", "sort", "create_time"]
    search_fields = ["name", "course__name"]
    list_filter = ["chapter_type", "course__category"]
    list_editable = ["sort"]

class LearningRecordAdmin(admin.ModelAdmin):
    """学习记录Admin（移除不存在的learn_time，替换为create_time）"""
    list_display = ["employee", "chapter", "is_completed", "create_time"]
    search_fields = ["employee__employee_id", "chapter__name"]
    list_filter = ["is_completed", "chapter__course__category"]

class EmployeeAdmin(admin.ModelAdmin):
    """员工Admin（移除不存在的name/is_active，保留模型实际字段）"""
    list_display = ["employee_id", "department", "create_time"]
    search_fields = ["employee_id", "department"]
    list_filter = ["department"]

# ===================== 模型注册（仅注册一次，无重复）=====================
# 核心：每个模型只通过admin.site.register注册一次，无装饰器/重复注册
admin.site.register(CourseCategory, CourseCategoryAdmin)
admin.site.register(Course, CourseAdmin)
admin.site.register(CourseChapter, CourseChapterAdmin)
admin.site.register(CourseResource, CourseResourceAdmin)
admin.site.register(LearningRecord, LearningRecordAdmin)
admin.site.register(Employee, EmployeeAdmin)