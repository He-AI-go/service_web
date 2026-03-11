# training/urls.py
from django.urls import path
from . import views

# 正确的urlpatterns：仅包含path()实例，注释写在列表外/列表内单行
urlpatterns = [
    # 首页 = 课程列表页
    path('', views.course_list, name='course_list'),

    # 课程详情页
    path('course/<int:course_id>/', views.course_detail, name='course_detail'),

    # 视频播放页（核心，带章节ID，控制学习路径）
    path('video/play/<int:chapter_id>/', views.video_play, name='video_play'),

    # 视频播放完成后标记学习记录（AJAX请求）
    path('video/complete/<int:chapter_id>/', views.video_complete, name='video_complete'),

    # 文档学习/预览页
    path('document/preview/<int:chapter_id>/', views.document_preview, name='document_preview'),

    # 视频资源访问（类视图）
    path('video/<int:resource_id>/', views.CourseVideoView.as_view(), name='course_video'),

    # 更新学习状态（类视图）
    path('update_learning_status/', views.UpdateLearningStatusView.as_view(), name='update_learning_status'),

    # 校验学习路径（类视图）
    path('check_learning_path/', views.CheckLearningPathView.as_view(), name='check_learning_path'),
]