from django.contrib import admin
from .models import *

# 1. ERP同步日志（管理员后台，只读为主）
@admin.register(ERPSyncLog)
class ERPSyncLogAdmin(admin.ModelAdmin):
    list_display = ['sync_time', 'sync_status', 'sync_count', 'fail_reason']
    list_filter = ['sync_status']
    search_fields = ['fail_reason']
    readonly_fields = ['sync_time', 'sync_status', 'sync_count', 'fail_reason']  # 只读，防止误改

# 2. 员工信息（从ERP同步，后台仅查看/改状态）
@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['employee_id', 'username', 'department', 'status', 'sync_time']
    list_filter = ['status', 'department']
    search_fields = ['employee_id', 'username']
    fieldsets = (
        ("员工基本信息", {"fields": ("employee_id", "username", "department", "status")}),
        ("同步信息（只读）", {"fields": ("sync_time", "create_time")}),
    )
    readonly_fields = ['sync_time', 'create_time']

# 3. 课程分类（极简版，适合非技术人员）
@admin.register(CourseCategory)
class CourseCategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "sort", "create_time"]
    list_editable = ["sort"]  # 列表页直接改排序
    search_fields = ["name"]
    fields = ["name", "sort"]  # 只显示必填字段
    readonly_fields = ["create_time"]

# 4. 课程章节内嵌（编辑课程时直接加章节）
class CourseChapterInline(admin.TabularInline):
    model = CourseChapter
    extra = 1  # 默认显示1个空白章节
    fields = ["name", "chapter_type", "resource", "sort"]
    verbose_name = "课程章节"
    verbose_name_plural = "课程章节"

# 5. 课程管理（核心：内嵌章节，简化字段）
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name',)
    list_filter = ["category", "difficulty"]
    search_fields = ["name"]
    inlines = [CourseChapterInline]  # 内嵌章节编辑
    fieldsets = (
        ("基本信息（必填）", {"fields": ("name", "category", "difficulty", "intro")}),
        ("系统自动信息（不用改）", {"fields": ("learn_count", "create_time", "update_time"), "classes": ("collapse",)}),
    )
    readonly_fields = ["learn_count", "create_time", "update_time"]  # 只读字段

# 6. 课程资料（自动识别文件类型，极简）
@admin.register(CourseResource)
class CourseResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'course', 'file_type', 'chapter')  # 确保这些字段都在模型中存在
    list_filter = ('file_type', 'course', 'chapter')  # 确保字段存在且是可过滤的类型
    search_fields = ["name"]
    fields = ["course", "name", "file_path"]  # 仅显示需要手动填的字段
    readonly_fields = []  # 系统自动生成

# 7. 课程章节（单独管理入口，备用）
@admin.register(CourseChapter)
class CourseChapterAdmin(admin.ModelAdmin):
    list_display = ('name', 'resource', 'sort')
    list_filter = ["chapter_type", "course"]
    list_editable = ["sort"]  # 列表页直接改排序
    search_fields = ["name"]
    fields = ["course", "name", "chapter_type", "resource", "sort"]
    readonly_fields = ["create_time"]

# 8. 学习记录（仅查看，不允许修改）
@admin.register(LearningRecord)
class LearningRecordAdmin(admin.ModelAdmin):
    list_display = ['employee', 'chapter', 'is_completed', 'complete_time']
    list_filter = ['is_completed']
    search_fields = ['employee__username', 'chapter__name']
    readonly_fields = ['employee', 'chapter', 'is_completed', 'complete_time', 'create_time']

# 9. 考题管理（备用，暂时不用可注释）
@admin.register(ExamQuestion)
class ExamQuestionAdmin(admin.ModelAdmin):
    list_display = ['course', 'question_type', 'content', 'score', 'generate_time']
    list_filter = ['question_type', 'course']
    search_fields = ['content']
    readonly_fields = ['generate_time']

# 10. 考试答卷（仅查看）
@admin.register(ExamPaper)
class ExamPaperAdmin(admin.ModelAdmin):
    list_display = ['employee', 'course', 'total_score', 'answer_time']
    list_filter = ['course']
    search_fields = ['employee__username', 'course__name']
    readonly_fields = ['employee', 'course', 'total_score', 'answer_time']

# 11. 答题明细（仅查看）
@admin.register(ExamAnswerDetail)
class ExamAnswerDetailAdmin(admin.ModelAdmin):
    list_display = ['paper', 'question', 'employee_answer', 'is_correct', 'score']
    list_filter = ['is_correct']
    search_fields = ['question__content']
    readonly_fields = ['paper', 'question', 'employee_answer', 'is_correct', 'score']