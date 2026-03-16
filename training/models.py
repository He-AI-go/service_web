from django.db import models
from django.core.validators import FileExtensionValidator
import os
from django.db.models.signals import post_save
from django.dispatch import receiver


# 保留你原有导入（若knowledge_utils.py不存在，需确保后续创建或注释）
# from .knowledge_utils import add_single_file_to_kb

# -------------------------- 原有模型&枚举类（完全保留，无修改）--------------------------
# 文档上传模型（管理员上传新文档用）
class TrainingDocument(models.Model):
    title = models.CharField(max_length=200, verbose_name="文档标题")
    file = models.FileField(upload_to="training_docs/", verbose_name="上传文件")  # 保存到 media/training_docs/
    upload_time = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    class Meta:
        verbose_name = "培训文档"
        verbose_name_plural = "培训文档"

    def __str__(self):
        return self.title


# -------------------------- 原有信号（完全保留）--------------------------
@receiver(post_save, sender=TrainingDocument)
def trigger_incremental_kb_update(sender, instance, created, **kwargs):
    """新文件上传（created=True）时，触发增量更新知识库"""
    if created:  # 仅对新创建的文件生效（避免编辑时重复处理）
        file_path = instance.file.path
        if os.path.exists(file_path):
            print(f"📁 检测到新上传文件：{instance.file.name}，触发增量更新...")
            # 保留原有逻辑（若knowledge_utils.py未创建，建议先注释，后续补全）
            # add_single_file_to_kb(file_path)


# 通用枚举定义（抽离复用，完全保留）
class StatusChoices(models.TextChoices):
    """通用状态枚举：启用/禁用"""
    ENABLE = "1", "启用"
    DISABLE = "0", "禁用"


class CourseDifficultyChoices(models.TextChoices):
    """课程难度枚举"""
    PRIMARY = "primary", "初级"
    MIDDLE = "middle", "中级"


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


# 新增缺失枚举类（不影响原有逻辑，为考试功能依赖）
class QuestionTypeChoices(models.TextChoices):
    """考题类型枚举（新增，无冲突）"""
    SINGLE = "single", "单选题"
    MULTIPLE = "multiple", "多选题"
    JUDGE = "judge", "判断题"
    FILL = "fill", "填空题"


# 1. 员工表：完全保留
class Employee(models.Model):
    employee_id = models.CharField(
        max_length=20, unique=True, verbose_name="员工工号", primary_key=True
    )
    username = models.CharField(max_length=50, verbose_name="员工姓名")
    password = models.CharField(max_length=128, verbose_name="登录密码")
    department = models.CharField(max_length=50, null=True, blank=True, verbose_name="所属部门")
    status = models.CharField(
        max_length=1, choices=StatusChoices.choices, default=StatusChoices.DISABLE, verbose_name="员工状态"
    )
    sync_time = models.DateTimeField(auto_now=True, verbose_name="最后同步时间")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="本地创建时间")

    class Meta:
        db_table = "employee"
        verbose_name = "员工信息"
        verbose_name_plural = verbose_name
        ordering = ["employee_id"]

    def __str__(self):
        return f"{self.employee_id}-{self.username}"


# 2. 课程分类表：完全保留
class CourseCategory(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="分类名称")
    sort = models.IntegerField(default=0, verbose_name="排序值")  # 前端展示排序
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "course_category"
        verbose_name = "课程分类"
        verbose_name_plural = verbose_name
        ordering = ["sort"]

    def __str__(self):
        return self.name


# 3. 课程表：完全保留
class Course(models.Model):
    name = models.CharField(max_length=200, unique=True, verbose_name="课程名称")
    category = models.ForeignKey(
        CourseCategory, on_delete=models.CASCADE, related_name="courses", verbose_name="所属分类"
    )
    learn_count = models.IntegerField(default=0, verbose_name="学习人数")
    difficulty = models.CharField(
        max_length=10, choices=CourseDifficultyChoices.choices, default=CourseDifficultyChoices.PRIMARY,
        verbose_name="课程难度"
    )
    intro = models.TextField(verbose_name="课程介绍")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "course"
        verbose_name = "课程信息"
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


# 4. 课程资料表：完全保留（含save自动计算文件大小）
class CourseResource(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="resources", verbose_name="所属课程"
    )
    name = models.CharField(max_length=200, verbose_name="资料名称")
    file_type = models.CharField(
        max_length=10, choices=FileTypeChoices.choices, verbose_name="文件类型"
    )
    file_path = models.FileField(
        upload_to="course_resources/%Y/%m/%d/",  # 按年月存储
        verbose_name="文件本地路径",
        validators=[FileExtensionValidator(allowed_extensions=["mp4", "ppt", "pptx", "doc", "docx", "pdf", "xlsx"])]
    )
    file_size = models.BigIntegerField(verbose_name="文件大小(字节)")
    upload_time = models.DateTimeField(auto_now_add=True, verbose_name="上传时间")

    def save(self, *args, **kwargs):
        # 自动获取文件大小，无需管理员手动输入（完全保留）
        self.file_size = self.file_path.size
        super().save(*args, **kwargs)

    class Meta:
        db_table = "course_resource"
        verbose_name = "课程资料"
        verbose_name_plural = verbose_name
        unique_together = ("course", "name")  # 同一课程下资料名称唯一

    def __str__(self):
        return f"{self.course.name}-{self.name}"


# 5. 课程章节表：完全保留（含parent外键实现章节-子章节）
class CourseChapter(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="chapters", verbose_name="所属课程"
    )
    resource = models.OneToOneField(
        CourseResource, on_delete=models.CASCADE, related_name="chapter", verbose_name="关联资料"
    )
    name = models.CharField(max_length=200, verbose_name="章节/子章节名称")
    chapter_type = models.CharField(
        max_length=10, choices=ChapterTypeChoices.choices, verbose_name="章节类型"
    )
    sort = models.IntegerField(default=0, verbose_name="排序值")  # 排序值越小越靠前
    parent = models.ForeignKey(
        'self', on_delete=models.CASCADE, null=True, blank=True,
        related_name="sub_chapters", verbose_name="父章节"
    )  # null=一级章节，非null=子章节
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "course_chapter"
        verbose_name = "课程章节"
        verbose_name_plural = verbose_name
        unique_together = ("course", "sort", "parent")  # 同一课程+同父章节，排序值唯一

    def __str__(self):
        if self.parent:
            return f"{self.course.name}-{self.parent.name}-子章节：{self.name}"
        return f"{self.course.name}-一级章节：{self.name}"


# 6. 学习记录表：完全保留（移除内部嵌套模型，修正语法错误）
class LearningRecord(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="learning_records", verbose_name="所属员工"
    )
    chapter = models.ForeignKey(
        CourseChapter, on_delete=models.CASCADE, related_name="learning_records", verbose_name="所属章节"
    )
    is_completed = models.BooleanField(default=False, verbose_name="是否完成")
    complete_time = models.DateTimeField(null=True, blank=True, verbose_name="完成时间")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="记录创建时间")

    class Meta:
        db_table = "learning_record"
        verbose_name = "学习记录"
        verbose_name_plural = verbose_name
        unique_together = ("employee", "chapter")  # 同一员工对同一章节仅一条记录

    def __str__(self):
        return f"{self.employee.username}-{self.chapter.name}-{'已完成' if self.is_completed else '未完成'}"


# -------------------------- 新增模型（独立存在，不影响原有逻辑）--------------------------
# 1. 教师/课程负责人模型（原嵌套在LearningRecord内，移至外部）
class CourseTeacher(models.Model):
    """教师/课程负责人信息（教师介绍板块）"""
    course = models.OneToOneField(
        Course, on_delete=models.CASCADE, related_name="teacher", verbose_name="所属课程"
    )
    name = models.CharField(max_length=50, verbose_name="姓名")
    title = models.CharField(max_length=100, verbose_name="职称/岗位")
    intro = models.TextField(verbose_name="简介")  # 如擅长领域、教学经验
    contact = models.CharField(max_length=100, null=True, blank=True, verbose_name="联系方式")  # 内部联系方式
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="创建时间")

    class Meta:
        db_table = "course_teacher"
        verbose_name = "课程教师"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.course.name}-{self.name}"


# 2. 学习交流模型（原嵌套在LearningRecord内，移至外部）
class CourseDiscussion(models.Model):
    """学习交流（课程通知/学习Tips，替代员工评价）"""
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="discussions", verbose_name="所属课程"
    )
    title = models.CharField(max_length=200, verbose_name="标题")
    content = models.TextField(verbose_name="内容")
    is_notice = models.BooleanField(default=False, verbose_name="是否为官方通知")  # 管理员/教师发布的通知
    creator = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="created_discussions", verbose_name="发布人"
    )
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="发布时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "course_discussion"
        verbose_name = "学习交流"
        verbose_name_plural = verbose_name
        ordering = ["-is_notice", "-create_time"]  # 通知优先，按时间倒序

    def __str__(self):
        return f"{self.course.name}-{self.title}"


# 3. 答疑问题模型（原嵌套在LearningRecord内，移至外部）
class CourseQuestion(models.Model):
    """学习答疑-问题表（贴吧式问题）"""
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="qa_questions", verbose_name="所属课程"
    )
    title = models.CharField(max_length=200, verbose_name="问题标题")
    content = models.TextField(verbose_name="问题详情")
    creator = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="created_qa_questions", verbose_name="提问人"
    )
    is_solved = models.BooleanField(default=False, verbose_name="是否已解决")
    view_count = models.IntegerField(default=0, verbose_name="浏览次数")
    like_count = models.IntegerField(default=0, verbose_name="点赞数")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="提问时间")
    update_time = models.DateTimeField(auto_now=True, verbose_name="更新时间")

    class Meta:
        db_table = "course_qa_question"
        verbose_name = "答疑问题"
        verbose_name_plural = verbose_name
        ordering = ["-is_solved", "-create_time"]  # 未解决优先，按时间倒序

    def __str__(self):
        return f"{self.course.name}-{self.title}"


# 4. 问题回复模型（原嵌套在LearningRecord内，移至外部）
class CourseAnswer(models.Model):
    """学习答疑-回复表（问题回复）"""
    question = models.ForeignKey(
        CourseQuestion, on_delete=models.CASCADE, related_name="answers", verbose_name="关联问题"
    )
    content = models.TextField(verbose_name="回复内容")
    creator = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="created_qa_answers", verbose_name="回复人"
    )
    is_accepted = models.BooleanField(default=False, verbose_name="是否为最佳答案")  # 提问人可采纳
    like_count = models.IntegerField(default=0, verbose_name="点赞数")
    create_time = models.DateTimeField(auto_now_add=True, verbose_name="回复时间")

    class Meta:
        db_table = "course_qa_answer"
        verbose_name = "问题回复"
        verbose_name_plural = verbose_name
        ordering = ["-is_accepted", "-create_time"]  # 最佳答案优先

    def __str__(self):
        return f"{self.question.title}-{self.creator.username}"


# 5. 考题模型（新增，关联课程和文档）
class ExamQuestion(models.Model):
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="questions", verbose_name="所属课程"
    )
    resource = models.ForeignKey(  # 关联生成题目的文档
        CourseResource, on_delete=models.CASCADE, related_name="questions", verbose_name="关联文档"
    )
    question_type = models.CharField(
        max_length=10, choices=QuestionTypeChoices.choices, verbose_name="考题类型"
    )
    content = models.TextField(verbose_name="题目内容")
    correct_answer = models.TextField(verbose_name="正确答案")  # 多选存为逗号分隔，判断存"True/False"，填空存关键词（逗号分隔）
    score = models.DecimalField(
        max_digits=3, decimal_places=1, default=1.0, verbose_name="题目分值"
    )
    generate_time = models.DateTimeField(auto_now_add=True, verbose_name="AI生成时间")

    class Meta:
        db_table = "exam_question"
        verbose_name = "考题信息"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.course.name}-{self.get_question_type_display()}-{self.content[:20]}"


# 6. 课程完成状态模型（新增，标记是否通过考试）
class CourseComplete(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="completed_courses", verbose_name="所属员工"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="completed_employees", verbose_name="完成课程"
    )
    exam_score = models.DecimalField(
        max_digits=5, decimal_places=1, verbose_name="考试分数"
    )
    is_passed = models.BooleanField(default=False, verbose_name="是否通过")
    complete_time = models.DateTimeField(auto_now_add=True, verbose_name="完成时间")

    class Meta:
        db_table = "course_complete"
        verbose_name = "课程完成状态"
        verbose_name_plural = verbose_name
        unique_together = ("employee", "course")  # 同一员工对同一课程仅一条记录

    def __str__(self):
        return f"{self.employee.username}-{self.course.name}-{'通过' if self.is_passed else '未通过'}"

class ExamPaper(models.Model):
    """考试答卷表"""
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="exam_papers", verbose_name="参考员工"
    )
    course = models.ForeignKey(
        Course, on_delete=models.CASCADE, related_name="exam_papers", verbose_name="考试课程"
    )
    total_score = models.DecimalField(
        max_digits=5, decimal_places=1, default=0.0, verbose_name="考试总分"
    )
    answer_time = models.DateTimeField(auto_now_add=True, verbose_name="答题时间")

    class Meta:
        db_table = "exam_paper"
        verbose_name = "考试答卷"
        verbose_name_plural = verbose_name

    def __str__(self):
        return f"{self.employee.username}-{self.course.name}-{self.total_score}分"


class ExamAnswerDetail(models.Model):
    """考试答题明细表"""
    paper = models.ForeignKey(
        ExamPaper, on_delete=models.CASCADE, related_name="answer_details", verbose_name="所属答卷"
    )
    question = models.ForeignKey(
        ExamQuestion, on_delete=models.CASCADE, verbose_name="关联考题"
    )
    employee_answer = models.TextField(verbose_name="员工答案")
    is_correct = models.BooleanField(default=False, verbose_name="是否正确")
    score = models.DecimalField(
        max_digits=3, decimal_places=1, default=0.0, verbose_name="本题得分"
    )

    class Meta:
        db_table = "exam_answer_detail"
        verbose_name = "考试答题明细"
        verbose_name_plural = verbose_name
        unique_together = ("paper", "question")  # 同一答卷对同一考题仅一条记录

    def __str__(self):
        return f"{self.paper.employee.username}-{self.question.content[:20]}-{'正确' if self.is_correct else '错误'}"