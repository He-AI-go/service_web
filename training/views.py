# ==============================================
# 核心 Django 基础导入（按功能分类，统一放置顶部）
# ==============================================
from django.shortcuts import render, redirect, reverse, get_object_or_404
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.db.models import Count, Sum, Q
from django.db.models.functions import Coalesce
from django.contrib.auth import authenticate, login as dj_login, logout as dj_logout
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# ==============================================
# 自定义模块/装饰器/工具导入
# ==============================================
from .models import (
    Employee, CourseCategory, Course, CourseChapter,
    CourseResource, LearningRecord, ChapterTypeChoices,
    CourseTeacher, CourseDiscussion, CourseQuestion, CourseAnswer,
    ExamQuestion, CourseComplete,ExamAnswerDetail,ExamPaper)
from training.models import CourseDiscussion

# 正确写法（匹配models.py中定义的模型名）
from training.models import CourseComment

from .decorators import (
    employee_login_required,
    admin_login_required,
    course_stat_view_required
)
from .knowledge_utils import retrieve_knowledge

# ==============================================
# 第三方库导入（按使用频率/功能分组）
# ==============================================
# OpenAI 相关
from openai import OpenAI

# 环境变量配置
import os
from dotenv import load_dotenv

# 文件解析相关（PDF/Word/PPT）
from PyPDF2 import PdfReader
from docx import Document
from pptx import Presentation

# 向量检索/嵌入相关
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# 缓存/哈希相关
import hashlib

# 加载环境变量
load_dotenv()

# 英伟达API配置（核心优化：换8B小模型！）
client = OpenAI(
    api_key=os.getenv("NVIDIA_API_KEY"),
    base_url=os.getenv("NVIDIA_BASE_URL")
)
# 关键修改：70B→8B小模型（CPU推理快10倍+）
MODEL_NAME = "meta/llama-3.1-70b-instruct"
MAX_HISTORY_COUNT = 11  # 优化：保留5轮上下文（减少上下文长度）
user_sessions = {}
answer_cache = {}  # 新增：问题缓存（key=问题哈希，value=答案）
CACHE_EXPIRE_TIME = 3600  # 缓存有效期1小时

# 默认系统提示（固定，不动态修改）
SYSTEM_PROMPT = """你是公司物流培训AI客服，回答规则如下：
1. 严格根据提供的本地培训文档内容作答，语言简洁、专业、只讲中文；
2. 找到答案后，必须在回答开头标注【资料来源：XXX文档】（XXX为文档文件名）；
3. 若文档中无相关内容，直接说「抱歉，我暂时无法回答这个问题」，不编造内容；
4. 回答条理清晰，不要多余标点和换行。"""

# 新增：生成问题的哈希值（缓存key）
def get_question_hash(question):
    return hashlib.md5(question.encode("utf-8")).hexdigest()

@csrf_exempt
def chat_api(request):
    if request.method != "POST":
        return JsonResponse({"code": 400, "msg": "仅支持POST请求"}, status=400)

    question = request.POST.get("question", "").strip()
    if not question:
        return JsonResponse({"code": 400, "msg": "问题不能为空"}, status=400)

    # 第一步：优先查缓存（重复问题直接返回，0秒响应）
    q_hash = get_question_hash(question)
    if q_hash in answer_cache:
        cached_answer = answer_cache[q_hash]
        return JsonResponse({
            "code": 200,
            "msg": "success（缓存）",
            "data": {"answer": cached_answer}
        })

    # 用户会话ID
    user_id = request.session.session_key or "default_user"
    if not request.session.session_key:
        request.session.save()

    # 初始化对话历史（优化：system prompt固定，不动态修改）
    if user_id not in user_sessions:
        user_sessions[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]

    # 第二步：检索知识库（优化：只取前3条，减少拼接内容）
    relevant_knowledge = retrieve_knowledge(question, top_k=3)  # 原top_k=5→3
    knowledge_text = ""
    if relevant_knowledge:
        # 优化：简化拼接格式，减少冗余字符
        for item in relevant_knowledge:
            knowledge_text += f"【{item['source']}】：{item['content']}\n"

    # 第三步：构造调用消息（核心优化：知识库内容作为user消息的一部分，而非修改system）
    # 这样既传递了知识库，又不污染system prompt，减少上下文长度
    user_msg = f"我的问题：{question}\n\n参考培训文档：\n{knowledge_text}" if knowledge_text else question
    user_sessions[user_id].append({"role": "user", "content": user_msg})

    # 限制上下文长度（优化：5轮=11条消息，比原10轮更少）
    if len(user_sessions[user_id]) > MAX_HISTORY_COUNT:
        # 保留system + 最后10条（5轮）
        user_sessions[user_id] = [user_sessions[user_id][0]] + user_sessions[user_id][-10:]

    try:
        # 第四步：调用API（优化参数：降低max_tokens、调快temperature）
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=user_sessions[user_id],
            temperature=0.3,  # 原0.5→0.3（推理更快，答案更稳定）
            max_tokens=500,   # 原800→500（减少生成字数，提速）
            timeout=10        # 原15→10（缩短超时，避免等待）
        )

        answer = response.choices[0].message.content.strip()
        user_sessions[user_id].append({"role": "assistant", "content": answer})

        # 新增：存入缓存
        answer_cache[q_hash] = answer

        return JsonResponse({
            "code": 200,
            "msg": "success",
            "data": {"answer": answer}
        })

    except Exception as e:
        # 缓存异常答案，避免重复报错
        error_answer = "抱歉，暂时无法回答你的问题，请稍后重试。"
        answer_cache[q_hash] = error_answer
        return JsonResponse({
            "code": 500,
            "msg": f"服务异常：{str(e)}",
            "data": {"answer": error_answer}
        })

def chat_iframe(request):
    return render(request, 'training/chat_iframe.html')

# ---------------------- 员工登录/注销 ----------------------
def employee_login(request):
    """员工登录页：工号+密码验证"""
    if request.method == 'GET':
        return render(request, 'training/login.html')
    # POST请求：验证工号密码
    employee_id = request.POST.get('employee_id')
    password = request.POST.get('password')
    if not all([employee_id, password]):
        return JsonResponse({'code': 400, 'msg': '工号和密码不能为空'})
    try:
        employee = Employee.objects.get(employee_id=employee_id, status=1)
    except Employee.DoesNotExist:
        return JsonResponse({'code': 404, 'msg': '工号不存在或账号已禁用'})
    # 验证密码（后续ERP同步后密码为加密，先做明文验证，简单可用）
    if employee.password != password:
        return JsonResponse({'code': 401, 'msg': '密码错误'})
    # 登录成功：保存工号到Session
    request.session['employee_id'] = employee.employee_id
    return JsonResponse({'code': 200, 'msg': '登录成功', 'url': reverse('training:course_list')})

def employee_logout(request):
    """员工注销：清除Session"""
    request.session.flush()
    return redirect(reverse('training:login'))

# ---------------------- 课程列表（核心入口） ----------------------
@employee_login_required
def course_list(request):
    """课程列表页：支持课程分类、难度筛选，展示所有课程"""
    # 1. 获取所有课程分类（按排序值展示）
    categories = CourseCategory.objects.all()
    # 2. 获取前端筛选参数
    cate_id = request.GET.get('cate_id', '')  # 分类ID
    difficulty = request.GET.get('difficulty', '')  # 难度（primary/middle）
    # 3. 构造筛选条件
    filter_kwargs = {}
    if cate_id:
        filter_kwargs['category_id'] = cate_id
    if difficulty:
        filter_kwargs['difficulty'] = difficulty
    # 4. 查询课程，预取关联的分类和一级章节
    courses = Course.objects.filter(**filter_kwargs).prefetch_related('category', 'chapters')
    # 5. 封装课程数据（前端展示用）
    course_data = []
    for course in courses:
        # 统计一级章节数量
        first_chapter_count = course.chapters.filter(parent__isnull=True).count()
        course_data.append({
            'id': course.id,
            'name': course.name,
            'category': course.category.name,
            'learn_count': course.learn_count,
            'difficulty': course.get_difficulty_display(),
            'difficulty_code': course.difficulty,
            'intro': course.intro[:80] + '...' if len(course.intro) > 80 else course.intro,
            'chapter_count': first_chapter_count
        })
    # 6. 渲染页面，传入筛选参数和数据
    context = {
        'categories': categories,
        'courses': course_data,
        'selected_cate': cate_id,
        'selected_diff': difficulty
    }
    return render(request, 'training/course_list.html', context)

# ---------------------- 课程章节-子章节层级 ----------------------
@employee_login_required
def course_chapter(request, course_id):
    """课程学习页：展示章节-子章节层级，点击进入播放/预览"""
    # 获取课程信息
    course = get_object_or_404(Course, id=course_id)
    # 查询一级章节，预取子章节、关联资料、学习记录
    first_chapters = CourseChapter.objects.filter(
        course_id=course_id, parent__isnull=True
    ).order_by('sort').prefetch_related('sub_chapters__resource', 'resource')
    #获取该课程的所有评价
    course_comments = course.comments.all()
    # 获取当前员工的所有学习记录
    learn_records = LearningRecord.objects.filter(
        employee=request.employee, chapter__course_id=course_id
    ).values('chapter_id', 'is_completed')
    # 转换为字典，方便前端判断
    learn_record_dict = {r['chapter_id']: r['is_completed'] for r in learn_records}
    # 封装章节-子章节数据
    chapter_data = []
    for first_cha in first_chapters:
        sub_chapters = first_cha.sub_chapters.order_by('sort')
        sub_cha_data = []
        for sub_cha in sub_chapters:
            sub_cha_data.append({
                'id': sub_cha.id,
                'name': sub_cha.name,
                'type': sub_cha.chapter_type,
                'type_name': sub_cha.get_chapter_type_display(),
                'resource_id': sub_cha.resource.id,
                'is_completed': learn_record_dict.get(sub_cha.id, False)
            })
        chapter_data.append({
            'id': first_cha.id,
            'name': first_cha.name,
            'type': first_cha.chapter_type,
            'type_name': first_cha.get_chapter_type_display(),
            'resource_id': first_cha.resource.id,
            'is_completed': learn_record_dict.get(first_cha.id, False),
            'sub_chapters': sub_cha_data
        })
    # 渲染页面
    context = {
        'course': course,
        'chapters': chapter_data,
        'course_comments': course_comments,  # 传递评价列表到模板
    }
    return render(request, 'training/course_chapter.html', context)

from django.contrib import messages
# 新增：添加课程评价视图
@login_required
def add_course_comment(request, course_id):
    # 获取课程对象，不存在则返回404
    course = get_object_or_404(Course, id=course_id)

    if request.method == 'POST':
        # 获取表单提交的评价内容
        content = request.POST.get('content', '').strip()
        if not content:
            messages.error(request, '评价内容不能为空！')
            return redirect('training:course_detail', pk=course_id)  # 跳回课程详情页

        # 创建评价记录（关联当前登录用户和课程）
        CourseComment.objects.create(
            course=course,
            user=request.user,  # 当前登录的员工
            content=content
        )
        messages.success(request, '评价发布成功！')
        return redirect('training:course_detail', pk=course_id)  # 发布后返回课程详情

    # GET请求时跳回课程详情（避免直接访问该URL）
    return redirect('training:course_detail', pk=course_id)
"""def add_course_comment(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            # 创建评价（当前登录用户为评价人）
            CourseComment.objects.create(
                course=course,
                creator=request.user,
                content=content
            )
    # 提交后返回课程详情页
    return redirect('training:course_chapter', course_id=course_id)"""


# 新增：评价点赞视图
@login_required
def like_course_comment(request, comment_id):
    comment = get_object_or_404(CourseComment, id=comment_id)
    # 切换点赞/取消点赞状态
    if request.user in comment.liked_users.all():
        comment.liked_users.remove(request.user)
        comment.like_count -= 1
    else:
        comment.liked_users.add(request.user)
        comment.like_count += 1
    comment.save()
    # 点赞后返回课程详情页
    return redirect('training:course_chapter', course_id=comment.course.id)

# ---------------------- 视频播放（核心功能） ----------------------
@employee_login_required
def video_play(request, chapter_id):
    """视频播放页：禁用拖放/倍速/下载，播放完成标记学习记录"""
    chapter = get_object_or_404(CourseChapter, id=chapter_id, chapter_type=ChapterTypeChoices.VIDEO)
    resource = chapter.resource
    # 渲染播放页
    context = {
        'chapter': chapter,
        'video_url': resource.file_path.url,  # 视频访问URL
        'course': chapter.course
    }
    return render(request, 'training/video_play.html', context)

# ---------------------- 文档预览（核心功能） ----------------------
@employee_login_required
def doc_preview(request, chapter_id):
    """文档预览页：仅预览，禁下载，打开即标记学习记录"""
    chapter = get_object_or_404(CourseChapter, id=chapter_id, chapter_type=ChapterTypeChoices.DOC)
    resource = chapter.resource
    # 打开文档即标记为完成（贴合需求：无需检测浏览时长）
    record, created = LearningRecord.objects.get_or_create(
        employee=request.employee,
        chapter=chapter,
        defaults={'is_completed': True, 'complete_time': timezone.now()}
    )
    if not created and not record.is_completed:
        record.is_completed = True
        record.complete_time = timezone.now()
        record.save()
    # 封装文档信息
    context = {
        'chapter': chapter,
        'doc_url': resource.file_path.url,
        'doc_type': resource.file_type,
        'course': chapter.course
    }
    return render(request, 'training/doc_preview.html', context)

# ---------------------- 学习记录标记（视频播放完成调用） ----------------------
@employee_login_required
def mark_learn_complete(request):
    """AJAX接口：视频播放完成后，标记章节为已完成"""
    if request.method != 'POST':
        return JsonResponse({'code': 405, 'msg': '仅支持POST请求'})
    chapter_id = request.POST.get('chapter_id')
    if not chapter_id:
        return JsonResponse({'code': 400, 'msg': '章节ID不能为空'})
    chapter = get_object_or_404(CourseChapter, id=chapter_id)
    # 创建/更新学习记录
    record, created = LearningRecord.objects.get_or_create(
        employee=request.employee,
        chapter=chapter,
        defaults={'is_completed': True, 'complete_time': timezone.now()}
    )
    if not created and not record.is_completed:
        record.is_completed = True
        record.complete_time = timezone.now()
        record.save()
    return JsonResponse({'code': 200, 'msg': '学习完成标记成功'})

# 管理员登录（复用Django admin验证）
def admin_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        admin = authenticate(request, username=username, password=password)
        if admin and admin.is_superuser and admin.is_active:
            dj_login(request, admin)
            request.session['admin_id'] = admin.id
            return JsonResponse({'code': 200, 'msg': '管理员登录成功', 'url': reverse('training:admin_dashboard')})
        return JsonResponse({'code': 401, 'msg': '管理员账号或密码错误'})
    return render(request, 'training/admin_login.html')

# 管理员注销
def admin_logout(request):
    dj_logout(request)
    request.session.flush()
    return redirect(reverse('training:admin_login'))


@employee_login_required
def my_learning_stat(request):
    """员工个人学习进度统计：AJAX接口，返回JSON数据"""
    employee = request.employee
    # 1. 统计员工所有有学习记录的课程
    learn_courses = Course.objects.filter(
        chapters__learning_records__employee=employee
    ).distinct().prefetch_related('chapters')
    # 2. 初始化统计数据
    total_course = learn_courses.count()  # 已参与课程数
    completed_course = 0  # 已完成课程数（所有章节完成）
    course_stat_list = []  # 各课程详情统计

    # 3. 遍历课程计算章节完成率
    for course in learn_courses:
        # 该课程总章节数
        total_chapter = course.chapters.count()
        # 该课程视频章节总数
        total_video_chapter = course.chapters.filter(type='video').count()
        # 该课程文档章节总数
        total_doc_chapter = course.chapters.filter(type='doc').count()
        # 员工已完成该课程章节数
        completed_chapter = LearningRecord.objects.filter(
            employee=employee,
            chapter__course=course,
            is_completed=True
        ).count()
        # 章节完成率（避免除0）
        chapter_complete_rate = round((completed_chapter / total_chapter) * 100, 2) if total_chapter > 0 else 0.0
        # 判断是否完成该课程
        is_course_completed = (completed_chapter == total_chapter) and (total_chapter > 0)
        if is_course_completed:
            completed_course += 1
        # 封装课程统计数据
        course_stat_list.append({
            'course_id': course.id,
            'course_name': course.name,
            'total_chapter': total_chapter,
            'completed_chapter': completed_chapter,
            'complete_rate': chapter_complete_rate,
            'is_completed': is_course_completed,
            'total_video_chapter': total_video_chapter,
            'total_doc_chapter': total_doc_chapter,
        })
    # 4. 个人总学习进度（已完成课程数/已参与课程数）
    total_complete_rate = round((completed_course / total_course) * 100, 2) if total_course > 0 else 0.0
    # 5. 返回JSON
    return JsonResponse({
        'code': 200,
        'data': {
            'total_course': total_course,
            'completed_course': completed_course,
            'uncompleted_course': total_course - completed_course,
            'total_complete_rate': total_complete_rate,
            'course_stat_list': course_stat_list
        }
    })

# 员工个人学习数据可视化页面
@employee_login_required
def my_learning_dashboard(request):
    """员工个人学习数据页：渲染ECharts可视化页面"""
    return render(request, 'training/employee_learning_stat.html')



@course_stat_view_required
def course_chapter_stat(request, course_id):
    """单课程章节完成率统计：AJAX接口，员工看个人，管理员看整体"""
    course = get_object_or_404(Course, id=course_id)
    # 该课程所有章节（按排序）
    chapters = course.chapters.order_by('sort').prefetch_related('learning_records')
    chapter_stat_list = []
    total_chapter = chapters.count()

    if request.is_admin:
        # 管理员视角：统计平台所有员工该章节的完成率
        for chapter in chapters:
            # 学习该章节的员工数
            learn_employee = chapter.learning_records.count()
            # 完成该章节的员工数
            completed_employee = chapter.learning_records.filter(is_completed=True).count()
            # 章节整体完成率
            complete_rate = round((completed_employee / learn_employee) * 100, 2) if learn_employee > 0 else 0.0
            chapter_stat_list.append({
                'chapter_id': chapter.id,
                'chapter_name': chapter.name,
                'learn_employee': learn_employee,
                'completed_employee': completed_employee,
                'complete_rate': complete_rate
            })
        # 课程整体统计
        course_total_learn = Employee.objects.filter(
            learning_records__chapter__course=course
        ).distinct().count()
        course_total_completed = Employee.objects.filter(
            Q(learning_records__chapter__course=course) & Q(learning_records__is_completed=True)
        ).annotate(
            completed_chapter=Count('learning_records__chapter', filter=Q(learning_records__chapter__course=course, learning_records__is_completed=True))
        ).filter(completed_chapter=total_chapter).count()
        course_complete_rate = round((course_total_completed / course_total_learn) * 100, 2) if course_total_learn > 0 else 0.0
    else:
        # 员工视角：统计个人该课程章节完成情况
        employee = request.employee
        for chapter in chapters:
            # 个人该章节完成状态
            is_completed = chapter.learning_records.filter(employee=employee, is_completed=True).exists()
            chapter_stat_list.append({
                'chapter_id': chapter.id,
                'chapter_name': chapter.name,
                'is_completed': is_completed
            })
        course_complete_rate = 0.0
        course_total_learn = 0
        course_total_completed = 0

    return JsonResponse({
        'code': 200,
        'data': {
            'course_name': course.name,
            'is_admin': request.is_admin,
            'course_complete_rate': course_complete_rate,
            'course_total_learn': course_total_learn,
            'chapter_stat_list': chapter_stat_list
        }
    })


@admin_login_required
def admin_dashboard_data(request):
    """管理员平台总览统计：AJAX接口，返回JSON数据供ECharts渲染"""
    # 1. 统计所有课程的学习人数、完成率
    courses = Course.objects.prefetch_related('chapters', 'learning_records__employee')
    course_data = []  # 课程柱状图/饼图数据
    total_learn_employee = Employee.objects.filter(
        learning_records__isnull=False
    ).distinct().count()  # 平台总学习员工数
    total_course = courses.count()  # 平台总课程数
    total_completed_course = 0  # 平台已完成（有员工完成）的课程数

    for course in courses:
        total_chapter = course.chapters.count()
        if total_chapter == 0:
            continue
        # 该课程学习人数（有任意学习记录的员工）
        learn_count = Employee.objects.filter(
            learning_records__chapter__course=course
        ).distinct().count()
        # 该课程完成人数（完成所有章节的员工）
        completed_count = Employee.objects.filter(
            Q(learning_records__chapter__course=course) & Q(learning_records__is_completed=True)
        ).annotate(
            completed_chapter=Count('learning_records__chapter', filter=Q(learning_records__chapter__course=course, learning_records__is_completed=True))
        ).filter(completed_chapter=total_chapter).count()
        # 课程完成率
        course_complete_rate = round((completed_count / learn_count) * 100, 2) if learn_count > 0 else 0.0
        if completed_count > 0:
            total_completed_course += 1
        # 封装课程数据（适配ECharts）
        course_data.append({
            'course_name': course.name,
            'learn_count': learn_count,
            'completed_count': completed_count,
            'complete_rate': course_complete_rate
        })

    # 2. 平台整体完成率（有完成的课程数/总课程数）
    platform_complete_rate = round((total_completed_course / total_course) * 100, 2) if total_course > 0 else 0.0

    # 3. 返回JSON（适配ECharts数据格式）
    return JsonResponse({
        'code': 200,
        'data': {
            'total_learn_employee': total_learn_employee,
            'total_course': total_course,
            'total_completed_course': total_completed_course,
            'platform_complete_rate': platform_complete_rate,
            # ECharts柱状图：学习人数
            'echarts_bar_x': [item['course_name'] for item in course_data],
            'echarts_bar_y': [item['learn_count'] for item in course_data],
            # ECharts饼图：课程完成率（按完成/未完成分组）
            'echarts_pie': [
                {'name': '已完成课程', 'value': total_completed_course},
                {'name': '未完成课程', 'value': total_course - total_completed_course}
            ],
            # 课程详细统计
            'course_detail': course_data
        }
    })

# 管理员平台总览可视化页面
@admin_login_required
def admin_dashboard(request):
    """管理员平台数据总览页：渲染ECharts可视化页面"""
    return render(request, 'training/admin_dashboard.html')


from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.core.cache import cache
from .models import CourseCategory, CourseResource
from .decorators import employee_login_required
from .utils.file_parser import QAParser
import os

# 缓存key：百问百答数据（有效期1小时，可调整）
QA_CACHE_KEY = "company_qa_data"


def load_qa_data_to_cache():
    """加载所有百问百答文件解析后的数据到缓存"""
    # 获取「百问百答」课程分类（管理员需先在后台创建该分类）
    try:
        qa_category = CourseCategory.objects.get(name="百问百答")
    except CourseCategory.DoesNotExist:
        return {"错误": [{"question": "未找到百问百答分类", "answer": "管理员需先在后台创建「百问百答」课程分类",
                          "category": "系统提示"}]}
    # 获取该分类下所有有效文件
    qa_resources = CourseResource.objects.filter(
        course__category=qa_category,
        file_type__in=["xlsx", "docx", "pdf"]
    )
    all_qa_data = {}
    for resource in qa_resources:
        file_path = os.path.join(settings.MEDIA_ROOT, str(resource.file_path))
        if not os.path.exists(file_path):
            continue
        # 解析文件
        file_qa = QAParser.parse_file(file_path, resource.file_type)
        # 合并数据
        for category, qa_list in file_qa.items():
            if category not in all_qa_data:
                all_qa_data[category] = []
            all_qa_data[category].extend(qa_list)
    # 缓存数据（有效期3600秒）
    cache.set(QA_CACHE_KEY, all_qa_data, 3600)
    return all_qa_data


@employee_login_required
def qa_chat(request):
    """AI客服问答接口：接收员工问题，返回匹配答案（关键词匹配）"""
    if request.method != "POST":
        return JsonResponse({"code": 405, "msg": "仅支持POST请求"})
    question = request.POST.get("question", "").strip()
    if not question:
        return JsonResponse({"code": 400, "msg": "请输入咨询问题"})

    # 从缓存获取问答数据（无则重新加载）
    qa_data = cache.get(QA_CACHE_KEY)
    if not qa_data:
        qa_data = load_qa_data_to_cache()

    # 关键词匹配（模糊匹配，优先完全匹配，再部分匹配）
    best_match = None
    max_score = 0
    for category, qa_list in qa_data.items():
        for qa in qa_list:
            # 计算匹配得分：完全匹配得10分，包含关键词得5分
            if question == qa["question"]:
                best_match = qa
                max_score = 10
                break
            elif all(keyword in qa["question"] for keyword in question.split()[:3]):  # 取前3个关键词
                score = len([k for k in question.split() if k in qa["question"]])
                if score > max_score:
                    max_score = score
                    best_match = qa
        if max_score == 10:
            break  # 完全匹配直接退出

    if best_match and max_score > 0:
        return JsonResponse({
            "code": 200,
            "data": {
                "question": best_match["question"],
                "answer": best_match["answer"],
                "category": best_match["category"]
            }
        })
    else:
        return JsonResponse({"code": 200, "data": {"question": question, "answer": "暂无相关解答，请联系管理员补充",
                                                   "category": "无匹配"}})


@employee_login_required
def qa_page(request):
    """百问百答页面：展示所有解析后的问答，支持分类筛选和搜索"""
    # 加载问答数据
    qa_data = cache.get(QA_CACHE_KEY)
    if not qa_data:
        qa_data = load_qa_data_to_cache()

    # 分类筛选
    categories = list(qa_data.keys())
    selected_cate = request.GET.get("cate", "")
    if selected_cate and selected_cate in qa_data:
        filtered_qa = qa_data[selected_cate]
    else:
        filtered_qa = [item for sublist in qa_data.values() for item in sublist]

    # 关键词搜索
    search_key = request.GET.get("search", "").strip()
    if search_key:
        filtered_qa = [
            qa for qa in filtered_qa
            if search_key in qa["question"] or search_key in qa["answer"]
        ]

    context = {
        "categories": categories,
        "selected_cate": selected_cate,
        "search_key": search_key,
        "qa_list": filtered_qa
    }
    return render(request, "training/qa_page.html", context)







###"""课程详情页：7大板块整合，强制学习路径+考试通过解锁下一课程"""
#1.. 课程详情页视图（整合 7 大板块）
@employee_login_required
def course_detail(request, course_id):
    """课程详情页：7大板块整合，强制学习路径+考试通过解锁下一课程"""
    course = get_object_or_404(Course, id=course_id)
    # 1. 课程章节（强制学习路径）
    chapters = CourseChapter.objects.filter(course=course).order_by('sort').prefetch_related('resource')
    # 2. 课程资料
    resources = CourseResource.objects.filter(course=course).order_by('-upload_time')
    # 3. 教师介绍

    teacher = CourseTeacher.objects.filter(course=course).first()
    # 1. 获取课程讨论
    discussions = CourseDiscussion.objects.filter(course=course).order_by('-create_time')
    # 2. 获取课程答疑问题
    qa_questions = CourseQuestion.objects.filter(course=course).order_by('-create_time')
    # 3. 判断是否有考题
    has_exam = ExamQuestion.objects.filter(course=course).exists()

    # 6. 考试相关
    exam_questions = ExamQuestion.objects.filter(course=course)
    has_exam = exam_questions.exists()
    # 7. 课程完成状态（判断是否通过考试）
    exam_paper = ExamPaper.objects.filter(employee=request.employee, course=course).order_by('-answer_time').first()
    is_course_passed = exam_paper.total_score >= 60 if exam_paper else False
    course_complete = exam_paper

    # 8. 下一课程（解锁逻辑：当前课程通过考试才显示）
    next_course = None
    current_category = course.category
    same_cate_courses = Course.objects.filter(category=current_category).order_by('id')
    try:
        course_index = list(same_cate_courses.values_list('id', flat=True)).index(course.id)
    except ValueError:
        course_index = -1
    if course_index != -1 and course_index < len(same_cate_courses) - 1 and is_course_passed:
        next_course = same_cate_courses[course_index + 1]

    # 9. 学习记录（章节完成状态）
    learn_records = LearningRecord.objects.filter(
        employee=request.employee, chapter__course=course
    ).values('chapter_id', 'is_completed')
    learn_record_dict = {r['chapter_id']: r['is_completed'] for r in learn_records}
    # 判断是否完成所有章节
    all_chapters_completed = all([learn_record_dict.get(ch.id, False) for ch in chapters]) if chapters.exists() else False

    context = {
        'course': course,
        'chapters': chapters,
        'resources': resources,
        'teacher': teacher,
        'discussions': discussions,
        'qa_questions': qa_questions,
        'has_exam': has_exam,
        'is_course_passed': is_course_passed,
        'all_chapters_completed': all_chapters_completed,
        'next_course': next_course,
        'course_complete': course_complete
    }
    return render(request, 'training/course_chapter.html', context)

#2.考试相关视图（自动阅卷 + 课程完成标记）
@employee_login_required
def course_exam(request, course_id):
    """课程考试页面：仅完成所有章节可进入"""
    course = get_object_or_404(Course, id=course_id)
    chapters = CourseChapter.objects.filter(course=course)
    # 校验是否完成所有章节
    all_chapters_completed = LearningRecord.objects.filter(
        employee=request.employee, chapter__course=course, is_completed=True
    ).count() == chapters.count() if chapters.exists() else False
    if not all_chapters_completed:
        return JsonResponse({'code': 403, 'msg': '请先完成所有章节学习再参加考试'}, status=403)

    # 获取考题（随机排序）
    exam_questions = ExamQuestion.objects.filter(course=course).order_by('?')
    if not exam_questions.exists():
        return JsonResponse({'code': 404, 'msg': '暂无考题，请联系管理员上传文档生成'}, status=404)

    if request.method == 'POST':
        # 考试提交：自动阅卷
        total_score = 0.0
        answer_details = []
        for question in exam_questions:
            employee_answer = request.POST.get(f'question_{question.id}', '').strip()
            is_correct = False
            score = 0.0

            # 按题型阅卷
            if question.question_type == 'single':
                # 单选题：精准匹配
                is_correct = employee_answer == question.correct_answer
                score = question.score if is_correct else 0.0
            elif question.question_type == 'multiple':
                # 多选题：按正确选项占比计分
                correct_options = set(question.correct_answer.split(','))
                employee_options = set(employee_answer.split(',')) if employee_answer else set()
                match_count = len(correct_options & employee_options)
                total_correct = len(correct_options)
                score = round(question.score * (match_count / total_correct), 1) if total_correct > 0 else 0.0
                is_correct = (match_count == total_correct)
            elif question.question_type == 'judge':
                # 判断题：精准匹配
                is_correct = employee_answer.lower() == question.correct_answer.lower()
                score = question.score if is_correct else 0.0
            elif question.question_type == 'fill':
                # 填空题：关键词匹配（匹配一个关键词得对应分值）
                correct_keywords = set(question.correct_answer.split(','))
                employee_keywords = set(employee_answer.split(',')) if employee_answer else set()
                match_count = len(correct_keywords & employee_keywords)
                total_keywords = len(correct_keywords)
                score = round(question.score * (match_count / total_keywords), 1) if total_keywords > 0 else 0.0
                is_correct = (match_count >= total_keywords * 0.6)  # 60%关键词匹配视为正确

            total_score += score
            answer_details.append({
                'question': question,
                'employee_answer': employee_answer,
                'correct_answer': question.correct_answer,
                'is_correct': is_correct,
                'score': score
            })

        # 标记课程完成状态（60分及格）
        is_passed = total_score >= 60
        exam_paper = ExamPaper.objects.create(
            employee=request.employee,
            course=course,
            total_score=total_score
        )
        for detail in answer_details:
            ExamAnswerDetail.objects.create(
                paper=exam_paper,
                question=detail['question'],
                employee_answer=detail['employee_answer'],
                is_correct=detail['is_correct'],
                score=detail['score']
            )

        context = {
            'course': course,
            'total_score': total_score,
            'is_passed': is_passed,
            'answer_details': answer_details
        }
        return render(request, 'training/exam_result.html', context)

    # GET请求：展示考试页面
    context = {
        'course': course,
        'exam_questions': exam_questions,
        'total_questions': exam_questions.count()
    }
    return render(request, 'training/course_exam.html', context)

#3. 学习答疑视图（贴吧式交互）
@employee_login_required
def qa_question_create(request, course_id):
    """发布答疑问题"""
    if request.method != 'POST':
        return JsonResponse({'code': 405, 'msg': '仅支持POST请求'})
    course = get_object_or_404(Course, id=course_id)
    title = request.POST.get('title', '').strip()
    content = request.POST.get('content', '').strip()
    if not title or not content:
        return JsonResponse({'code': 400, 'msg': '标题和内容不能为空'})

    CourseQuestion.objects.create(
        course=course,
        title=title,
        content=content,
        creator=request.employee
    )
    return JsonResponse(
        {'code': 200, 'msg': '问题发布成功', 'url': reverse('training:course_detail', args=[course_id])})


@employee_login_required
def qa_answer_create(request, question_id):
    """回复答疑问题"""
    if request.method != 'POST':
        return JsonResponse({'code': 405, 'msg': '仅支持POST请求'})
    question = get_object_or_404(CourseQuestion, id=question_id)
    content = request.POST.get('content', '').strip()
    if not content:
        return JsonResponse({'code': 400, 'msg': '回复内容不能为空'})

    answer = CourseAnswer.objects.create(
        question=question,
        content=content,
        creator=request.employee
    )
    # 提问人回复自动标记为已解决
    if request.employee == question.creator:
        question.is_solved = True
        question.save()
        answer.is_accepted = True
        answer.save()

    return JsonResponse({
        'code': 200,
        'msg': '回复成功',
        'url': reverse('training:course_detail', args=[question.course.id])
    })


@employee_login_required
def qa_question_accept(request, answer_id):
    """采纳最佳答案"""
    answer = get_object_or_404(CourseAnswer, id=answer_id)
    # 仅提问人可采纳
    if request.employee != answer.question.creator:
        return JsonResponse({'code': 403, 'msg': '无权限操作'})

    # 取消其他答案的采纳状态
    CourseAnswer.objects.filter(question=answer.question, is_accepted=True).update(is_accepted=False)
    # 标记当前答案为最佳
    answer.is_accepted = True
    answer.save()
    # 标记问题已解决
    answer.question.is_solved = True
    answer.question.save()

    return JsonResponse({
        'code': 200,
        'msg': '采纳成功',
        'url': reverse('training:course_detail', args=[answer.question.course.id])
    })

