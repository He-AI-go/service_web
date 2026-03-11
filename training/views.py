from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import *
import re


# 模拟员工登录（后续对接ERP同步后，替换为真实工号密码验证，内部系统简化）
# 实际开发时，可在中间件中实现登录验证，所有页面需登录后访问
def mock_login(request):
    # 模拟一个启用状态的员工（后续从ERP同步后，从Employee表查询）
    request.session['employee_id'] = '001'
    request.session['username'] = '张三'
    return redirect('course_list')


# 课程列表页（首页）- 核心展示所有课程，支持分类/难度筛选
def course_list(request):
    # 未登录则跳转到模拟登录
    if not request.session.get('employee_id'):
        return mock_login(request)

    # 获取筛选条件
    category_id = request.GET.get('category', '')
    difficulty = request.GET.get('difficulty', '')

    # 查询所有课程分类（用于前端筛选栏）
    categories = CourseCategory.objects.all()
    # 基础查询：所有启用状态课程（默认）
    courses = Course.objects.all()

    # 分类筛选
    if category_id and category_id.isdigit():
        courses = courses.filter(category_id=category_id)
    # 难度筛选
    if difficulty in [CourseDifficultyChoices.PRIMARY, CourseDifficultyChoices.MIDDLE]:
        courses = courses.filter(difficulty=difficulty)

    # 传递数据到前端模板
    context = {
        'categories': categories,
        'courses': courses,
        'selected_category': category_id,
        'selected_difficulty': difficulty,
        'username': request.session.get('username')
    }
    return render(request, 'training/course_list.html', context)


# 课程详情页-展示课程章节、资料，关联视频播放
def course_detail(request, course_id):
    if not request.session.get('employee_id'):
        return mock_login(request)

    # 获取课程信息，不存在则404
    course = get_object_or_404(Course, id=course_id)
    # 获取课程章节（按排序值升序，控制学习路径）
    chapters = CourseChapter.objects.filter(course=course).order_by('sort')
    # 获取当前员工（模拟，后续从Employee表查询）
    employee = get_object_or_404(Employee, employee_id=request.session.get('employee_id'))
    # 获取当前员工的学习记录
    learn_records = LearningRecord.objects.filter(employee=employee, chapter__in=chapters)
    # 构建章节完成状态字典，方便前端判断
    chapter_complete = {r.chapter.id: r.is_completed for r in learn_records}

    context = {
        'course': course,
        'chapters': chapters,
        'chapter_complete': chapter_complete,
        'username': request.session.get('username')
    }
    return render(request, 'training/course_detail.html', context)


# 视频播放页-核心，处理文件类型验证、学习路径控制
def video_play(request, chapter_id):
    if not request.session.get('employee_id'):
        return mock_login(request)

    # 1. 获取章节信息，不存在则404
    chapter = get_object_or_404(CourseChapter, id=chapter_id)
    # 2. 文件类型验证-核心解决文件类型报错：仅章节类型为视频的可访问
    if chapter.chapter_type != ChapterTypeChoices.VIDEO:
        return HttpResponse('当前不支持该文件类型，请尝试其他文件', status=400)
    # 3. 验证文件是否为MP4-双重保障，解决文件类型报错
    if chapter.resource.file_type != FileTypeChoices.MP4:
        return HttpResponse('当前不支持该文件类型，请尝试其他文件', status=400)

    # 4. 强制学习路径控制：判断是否为第一个章节，非第一个则验证上一章节是否完成
    course = chapter.course
    all_chapters = CourseChapter.objects.filter(course=course).order_by('sort')
    chapter_index = list(all_chapters).index(chapter)
    is_first_chapter = chapter_index == 0
    prev_chapter_complete = True

    if not is_first_chapter:
        # 获取上一章节
        prev_chapter = all_chapters[chapter_index - 1]
        # 获取当前员工学习记录
        employee = get_object_or_404(Employee, employee_id=request.session.get('employee_id'))
        prev_record = LearningRecord.objects.filter(employee=employee, chapter=prev_chapter).first()
        # 上一章节无记录或未完成，则跳回课程详情页并提示
        if not prev_record or not prev_record.is_completed:
            request.session['error_msg'] = '请先完成上一章节学习'
            return redirect('course_detail', course_id=course.id)

    # 5. 若当前章节无学习记录，创建空记录
    employee = get_object_or_404(Employee, employee_id=request.session.get('employee_id'))
    LearningRecord.objects.get_or_create(employee=employee, chapter=chapter)

    # 传递视频信息到前端
    context = {
        'chapter': chapter,
        'video_url': chapter.resource.file_path.url,  # 视频播放URL
        'course': course,
        'username': request.session.get('username'),
        'error_msg': request.session.pop('error_msg', '')
    }
    return render(request, 'training/video_play.html', context)


# 视频播放完成-标记学习记录为已完成（AJAX请求）
def video_complete(request, chapter_id):
    if not request.session.get('employee_id') or request.method != 'POST':
        return JsonResponse({'code': 403, 'msg': '权限不足'})

    try:
        chapter = get_object_or_404(CourseChapter, id=chapter_id)
        employee = get_object_or_404(Employee, employee_id=request.session.get('employee_id'))
        # 获取学习记录并更新
        record = LearningRecord.objects.get(employee=employee, chapter=chapter)
        record.is_completed = True
        record.complete_time = timezone.now()
        record.save()

        # 更新课程学习人数（若为该员工首次完成该课程任意章节，学习人数+1）
        course = chapter.course
        employee_course_records = LearningRecord.objects.filter(employee=employee, chapter__course=course,
                                                                is_completed=True)
        if employee_course_records.count() == 1:
            course.learn_count += 1
            course.save()

        return JsonResponse({'code': 200, 'msg': '学习完成'})
    except Exception as e:
        return JsonResponse({'code': 500, 'msg': f'标记失败：{str(e)}'})


def document_preview(request, chapter_id):
    if not request.session.get('employee_id'):
        return mock_login(request)

    # 获取章节信息
    chapter = get_object_or_404(CourseChapter, id=chapter_id)
    # 验证是文档类型章节
    if chapter.chapter_type != ChapterTypeChoices.DOC:
        return HttpResponse('当前不是文档章节', status=400)

    # 强制学习路径：必须完成上一章节
    course = chapter.course
    all_chapters = CourseChapter.objects.filter(course=course).order_by('sort')
    chapter_index = list(all_chapters).index(chapter)
    if chapter_index > 0:
        prev_chapter = all_chapters[chapter_index - 1]
        employee, created = Employee.objects.get_or_create(
            employee_id=request.session.get('employee_id'),
            defaults={'username': '测试员工', 'password': '123456', 'department': '测试', 'status': '1'}
        )
        prev_record = LearningRecord.objects.filter(employee=employee, chapter=prev_chapter).first()
        if not prev_record or not prev_record.is_completed:
            request.session['error_msg'] = '请先完成上一章节学习'
            return redirect('course_detail', course_id=course.id)

    # 自动创建学习记录
    employee, created = Employee.objects.get_or_create(
        employee_id=request.session.get('employee_id'),
        defaults={'username': '测试员工', 'password': '123456', 'department': '测试', 'status': '1'}
    )
    LearningRecord.objects.get_or_create(employee=employee, chapter=chapter)

    # 新增：本地解析Word文档内容
    document_content = ""
    file_type = chapter.resource.file_type
    file_path = chapter.resource.file_path.path  # 本地文件绝对路径

    if file_type in ["doc", "docx"]:
        try:
            from docx import Document
            doc = Document(file_path)
            # 提取所有段落内容
            document_content = "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            document_content = f"文档解析失败：{str(e)}"
    elif file_type == "pdf":
        # PDF仍用浏览器本地预览
        pass
    else:
        document_content = "暂不支持该格式本地预览，请上传Word/PDF文档"

    context = {
        'chapter': chapter,
        'document_url': chapter.resource.file_path.url,
        'document_type': file_type,
        'document_content': document_content,  # 传给前端的文档内容
        'course': course,
        'username': request.session.get('username'),
    }
    return render(request, 'training/document_preview.html', context)