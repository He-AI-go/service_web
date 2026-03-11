from django.db import models

# Create your models here.
from django.db import models
from django.core.validators import FileExtensionValidator
import os

# 通用枚举定义（抽离复用）
class StatusChoices(models.TextChoices):
    """通用状态枚举：启用/禁用"""
    ENABLE = "1", "启用"
    DISABLE = "0", "禁用"

class CourseDifficultyChoices(models.TextChoices):
    """课程难度枚举"""
    PRIMARY = "primary", "初级"
    MIDDLE = "middle", "中级"
# 课程资源类型枚举（提前定义，方便前后端统一）
class ResourceTypeChoices(models.TextChoices):
    VIDEO = 'video', '视频'
    DOC = 'doc', '文档'
    PPT = 'ppt', 'PPT'

class ChapterTypeChoices(models.TextChoices):
    """章节类型：视频/文档"""
    VIDEO = "video", "视频"
    DOC = "doc", "文档"

class FileTypeChoices(models.TextChoices):
    """文件类型枚举（贴合需求支持的格式）"""
    MP4 = "mp4", "MP4视频"
    PPT = "ppt", "PPT文档"
    PPTX = "pptx", "PPTX文档"
    DOC = "doc", "Word文档"
    DOCX = "docx", "WordX文档"
    PDF = "pdf", "PDF文档"
    EXCEL = "xlsx", "Excel表格"

class QuestionTypeChoices(models.TextChoices):
    """考题类型枚举"""
    SINGLE = "single", "单选题"
    MULTIPLE = "multiple", "多选题"
    FILL = "fill", "填空题"

class SyncStatusChoices(models.TextChoices):
    """ERP同步状态"""
    SUCCESS = "success", "成功"
    FAIL = "fail", "失败"

# 1. ERP员工同步日志表：记录每一次ERP同步的结果，排查同步失败问题
class ERPSyncLog(models.Model):
    sync_time = models.DateTimeField(auto_now_add=True, verbose_name="同步时间")
    sync_status = models.CharField(
        max_length=10, choices=SyncStatusChoices.choices, default=SyncStatusChoices.FAIL, verbose_name="同步状态"
    )
    fail_reason = models.TextField(null=True, blank=True, verbose_name="失败原因")
    sync_count = models.IntegerField(default=0, verbose_name="同步员工数量")  # 成功同步的员工数

    class Meta:
        db_table = "erp_sync_log"
        verbose_name = "ERP员工同步日志"
        verbose_name_plural = verbose_name
        ordering = ["-sync_time"]  # 按同步时间倒序

# 2. 员工表：核心，从ERP同步，无本地创建/修改功能
class Employee(models.Model):
    employee_id = models.CharField(
        max_length=20, unique=True, verbose_name="员工工号", primary_key=True  # 工号作为唯一主键，贴合ERP唯一标识
    )
    username = models.CharField(max_length=50, verbose_name="员工姓名")
    password = models.CharField(max_length=128, verbose_name="登录密码")  # 兼容加密密码存储
    department = models.CharField(max_length=50, null=True, blank=True, verbose_name="所属部门")
    status = models.CharField(
        max_length=1, choices=StatusChoices.choices, default=StatusChoices.DISABLE, verbose_name="员工状态"
    )
    sync_time = models.DateTimeField(auto_now=True, verbose_name="最后同步时间")  # ERP同步时更新
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="本地创建时间")

    class Meta:
        db_table = "employee"
        verbose_name = "员工信息"
        verbose_name_plural = verbose_name
        ordering = ["employee_id"]

    def __str__(self):
        return f"{self.employee_id}-{self.username}"

# 3. 课程分类表：培训分类（如国际物流专业知识、客服部工作流程）
# 课程分类表
class CourseCategory(models.Model):
    name = models.CharField(
        max_length=100, unique=True,
        verbose_name="分类名称",
        help_text="例如：国际物流专业知识、客服部工作流程"
    )
    sort = models.IntegerField(
        default=0,
        verbose_name="排序值",
        help_text="数字越小，分类在页面上越靠前（填 1、2、3... 即可）"
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "course_category"
        verbose_name = "课程分类"
        verbose_name_plural = verbose_name
        ordering = ["sort"]

    def __str__(self):
        return self.name

# 课程表
class Course(models.Model):
    name = models.CharField(
        max_length=200, unique=True,
        verbose_name="课程名称",
        help_text="例如：国际物流基础入门、仓库管理实操"
    )
    category = models.ForeignKey(
        CourseCategory, on_delete=models.CASCADE, related_name="courses",
        verbose_name="所属分类",
        help_text="从下拉框选一个刚才创建的分类"
    )
    learn_count = models.IntegerField(default=0, verbose_name="学习人数", editable=False)  # 系统自动算
    difficulty = models.CharField(
        max_length=10, choices=CourseDifficultyChoices.choices, default=CourseDifficultyChoices.PRIMARY,
        verbose_name="课程难度",
        help_text="选「初级」或「中级」"
    )
    intro = models.TextField(
        verbose_name="课程介绍",
        help_text="简单写几句课程讲什么，比如「适合新手学习的物流基础概念」"
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "course"
        verbose_name = "课程信息"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name

# 课程资料表（核心：自动识别文件类型，不用手动选）
class CourseResource(models.Model):
    """课程资源表（视频/文档）"""
    chapter = models.ForeignKey('CourseChapter', on_delete=models.CASCADE, verbose_name='所属章节')
    resource_type = models.CharField(
        max_length=10,
        choices=ResourceTypeChoices.choices,
        verbose_name='资源类型'
    )
    file = models.FileField(
        upload_to='course_resources/',
        verbose_name='资源文件',
        # 核心：添加文件后缀校验，解决文件类型报错
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    # 视频格式
                    'mp4', 'avi', 'mov',
                    # 文档格式
                    'doc', 'docx', 'pdf',
                    # PPT格式
                    'ppt', 'pptx'
                ],
                message='仅支持MP4/AVI/MOV（视频）、DOC/DOCX/PDF（文档）、PPT/PPTX格式！'
            )
        ]
    )
    file_size = models.BigIntegerField(verbose_name="文件大小", editable=False)  # 系统自动算
    upload_time = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    # 自动识别文件类型（管理员不用手动选）
    def save(self, *args, **kwargs):
        if self.file_path:
            ext = self.file_path.name.split(".")[-1].lower()
            type_map = {
                "mp4": FileTypeChoices.MP4,
                "ppt": FileTypeChoices.PPT,
                "pptx": FileTypeChoices.PPTX,
                "doc": FileTypeChoices.DOC,
                "docx": FileTypeChoices.DOCX,
                "pdf": FileTypeChoices.PDF,
                "xlsx": FileTypeChoices.EXCEL,
            }
            self.file_type = type_map.get(ext, FileTypeChoices.MP4)
            self.file_size = self.file_path.size  # 自动获取文件大小
        super().save(*args, **kwargs)

    class Meta:
        db_table = "course_resource"
        verbose_name = "课程资料"
        verbose_name_plural = verbose_name
        unique_together = ("course", "name")  # 同一课程下资料名称唯一

    def __str__(self):
        return f"{self.course.name}-{self.name}"

# 课程章节表
class CourseChapter(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="chapters",
        verbose_name="所属课程",
        help_text="选这个章节属于哪门课"
    )
    resource = models.OneToOneField(
        CourseResource, on_delete=models.CASCADE, related_name="chapter",
        verbose_name="关联资料",
        help_text="选刚才上传的视频/文档资料"
    )
    name = models.CharField(
        max_length=200,
        verbose_name="章节名称",
        help_text="和资料名称保持一致即可，比如「第一章 物流概述」"
    )
    chapter_type = models.CharField(
        max_length=10, choices=ChapterTypeChoices.choices,
        verbose_name="章节类型",
        help_text="视频资料选「视频」，文档资料选「文档」"
    )
    sort = models.IntegerField(
        default=0,
        verbose_name="章节排序",
        help_text="数字越小，学习顺序越靠前（第一章填 1，第二章填 2...）"
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "course_chapter"
        verbose_name = "课程章节"
        verbose_name_plural = verbose_name
        unique_together = ("course", "sort")  # 同一课程下排序值唯一，避免章节顺序重复

    def __str__(self):
        return f"{self.course.name}-第{self.sort}章-{self.name}"

# 7. 学习记录表：记录员工各章节的学习完成状态，核心用于强制学习路径判断
class LearningRecord(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="learning_records", verbose_name="所属员工"
    )
    chapter = models.ForeignKey(
        CourseChapter, on_delete=models.CASCADE, related_name="learning_records", verbose_name="所属章节"
    )
    is_completed = models.BooleanField(default=False, verbose_name="是否完成")  # 视频看完/文档打开即标记为True
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")
    play_progress = models.IntegerField(default=0, verbose_name='视频播放进度(秒)')
    class Meta:
        db_table = "learning_record"
        verbose_name = "学习记录"
        verbose_name_plural = verbose_name
        unique_together = ("employee", "chapter")  # 同一员工对同一章节仅一条记录

    def __str__(self):
        return f"{self.employee.username}-{self.chapter.name}-{'已完成' if self.is_completed else '未完成'}"

# 8-10表为考题/考试相关，本次重点开发视频学习板块，暂保留代码不做修改，后续可直接使用
class ExamQuestion(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="questions", verbose_name="所属课程"
    )
    question_type = models.CharField(
        max_length=10, choices=QuestionTypeChoices.choices, verbose_name="考题类型"
    )
    content = models.TextField(verbose_name="题目内容")
    correct_answer = models.TextField(verbose_name="正确答案")  # 多选存为逗号分隔（如A,B,C），填空存纯文本
    score = models.DecimalField(
        max_digits=3, decimal_places=1, default=1.0, verbose_name="题目分值"
    )  # 需求规定统一1分/题
    generate_time = models.DateTimeField(auto_now_add=True, verbose_name="AI生成时间")

    class Meta:
        db_table = "exam_question"
        verbose_name = "考题信息"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.course.name}-{self.get_question_type_display()}-{self.content[:20]}"

class ExamPaper(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="exam_papers", verbose_name="参考员工"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="exam_papers", verbose_name="考试课程"
    )
    total_score = models.DecimalField(
        max_digits=5, decimal_places=1, default=0.0, verbose_name="考试总分"
    )
    answer_time = models.DateTimeField(auto_now_add=True, verbose_name="作答时间")

    class Meta:
        db_table = "exam_paper"
        verbose_name = "考试答卷"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.employee.username}-{self.course.name}-{self.total_score}分"

class ExamAnswerDetail(models.Model):
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name="answer_details", verbose_name="所属答卷"
    )
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE, verbose_name="关联考题"
    )
    employee_answer = models.TextField(verbose_name="员工答案")  # 与正确答案格式一致
    is_correct = models.BooleanField(default=False, verbose_name="是否正确")
    score = models.DecimalField(
        max_digits=3, decimal_places=1, default=0.0, verbose_name="本题得分"
    )

    class Meta:
        db_table = "exam_answer_detail"
        verbose_name = "考试答题明细"
        verbose_name_plural = verbose_name
        unique_together = ("paper", "question")  # 同一答卷对同一考题仅一条明细

    def __str__(self):
        return f"{self.paper.employee.username}-{self.question.content[:20]}-{'正确' if self.is_correct else '错误'}"