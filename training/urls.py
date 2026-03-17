from django.urls import path
from . import views

app_name = 'training'

urlpatterns = [
    # 原有路由（登录/注销/课程/视频/文档）
    path('login/', views.employee_login, name='login'),
    path('logout/', views.employee_logout, name='logout'),
    path('', views.course_list, name='course_list'),
    path('course/chapter/<int:course_id>/', views.course_chapter, name='course_chapter'),
    path('video/play/<int:chapter_id>/', views.video_play, name='video_play'),
    path('doc/preview/<int:chapter_id>/', views.doc_preview, name='doc_preview'),
    path('mark/complete/', views.mark_learn_complete, name='mark_complete'),

    # 新增：管理员登录/注销
    path('admin/login/', views.admin_login, name='admin_login'),
    path('admin/logout/', views.admin_logout, name='admin_logout'),

    # 新增：员工个人学习数据
    path('employee/stat/', views.my_learning_dashboard, name='employee_learning_stat'),
    path('employee/stat/data/', views.my_learning_stat, name='my_learning_stat_data'),

    # 新增：课程章节完成率统计
    path('course/stat/<int:course_id>/', views.course_chapter_stat, name='course_chapter_stat'),

    # 新增：管理员平台总览
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/dashboard/data/', views.admin_dashboard_data, name='admin_dashboard_data'),
    path('qa/', views.qa_page, name='qa_page'),
    # 新增：AI客服问答接口
    path('qa/chat/', views.qa_chat, name='qa_chat'),
    path('chat-iframe/', views.chat_iframe, name='chat_iframe'),

    path('chat-api/', views.chat_api, name='chat_api'),  # 新增：客服消息接口
    path('course/detail/<int:course_id>/', views.course_detail, name='course_detail'),
    # 课程考试
    path('course/exam/<int:course_id>/', views.course_exam, name='course_exam'),
    # 学习答疑
    path('course/qa/question/<int:course_id>/create/', views.qa_question_create, name='qa_question_create'),
    path('course/qa/answer/<int:question_id>/create/', views.qa_answer_create, name='qa_answer_create'),
    path('course/qa/answer/<int:answer_id>/accept/', views.qa_question_accept, name='qa_answer_accept'),
    path('course/comment/add/<int:course_id>/', views.add_course_comment, name='add_course_comment'),
    path('course/comment/like/<int:comment_id>/', views.like_course_comment, name='like_course_comment'),

]