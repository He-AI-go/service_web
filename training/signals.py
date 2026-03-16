from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CourseResource
from .utils.ai_exam_generator import AIExamGenerator

# 文档上传后自动生成考题
@receiver(post_save, sender=CourseResource)
def course_resource_post_save(sender, instance, created, **kwargs):
    AIExamGenerator.generate_questions_on_resource_upload(sender, instance, created, **kwargs)