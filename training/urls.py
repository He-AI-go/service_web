from django.urls import path
from . import views

urlpatterns = [
    # 课程列表页（首页）
    path('', views.course_list, name='course_list'),
    # 课程详情页
    path('course/<int:course_id>/', views.course_detail, name='course_detail'),
    # 视频播放页（核心，带章节ID，控制学习路径）
    path('video/play/<int:chapter_id>/', views.video_play, name='video_play'),
    # 视频播放完成后标记学习记录（AJAX请求）
    path('video/complete/<int:chapter_id>/', views.video_complete, name='video_complete'),
    #文档学习
    path('document/preview/<int:chapter_id>/', views.document_preview, name='document_preview'),
    # 视频资源访问
    path('video/<int:resource_id>/', views.CourseVideoView.as_view(), name='course_video'),
    # 更新学习状态
    path('update_learning_status/', views.UpdateLearningStatusView.as_view(), name='update_learning_status'),
    # 校验学习路径
    path('check_learning_path/', views.CheckLearningPathView.as_view(), name='check_learning_path'),

]
