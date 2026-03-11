from django.shortcuts import render, redirect, HttpResponse, get_object_or_404
from django.http import JsonResponse
from django.utils import timezone
from .models import *
import re
from django.http import JsonResponse, FileResponse
from django.views import View
from .models import CourseChapter, CourseResource, LearningRecord, Employee
import os
from django.conf import settings


# 模拟员工登录（后续对接ERP同步后，替换为真实工号密码验证，内部系统简化）
# 实际开发时，可在中间件中实现登录验证，所有页面需登录后访问
def mock_login(request):
    # 模拟一个启用状态的员工（后续从ERP同步后，从Employee表查询）
    request.session['employee_id'] = '001'
    request.session['username'] = '张三'
    return redirect('course_list')


def course_list(request):
    # 按分类/难度查询所有课程，匹配需求中的展示规则
    courses = Course.objects.all().order_by('category__sort', 'name')
    # 传递课程数据给模板，键名建议用courses，模板中循环渲染
    context = {
        'courses': courses
    }
    # 渲染Django模板（不是纯静态HTML）
    return render(request, 'training/course_list.html', context)

# 章节详情视图（单独路由访问，不要和首页关联）
def chapter_detail(request, pk):
    from .models import CourseChapter
    chapter = CourseChapter.objects.get(pk=pk)
    context = {'chapter': chapter}
    return render(request, 'training/chapter_detail.html', context)


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
    file_path = chapter.resource.file_path  # 本地文件绝对路径

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


# 1. 视频资源访问接口（安全校验：仅登录员工可访问）
class CourseVideoView(View):
    def get(self, request, resource_id):
        # 简易登录校验（实际项目替换为Django auth）
        employee_id = request.GET.get('employee_id')
        if not employee_id or not Employee.objects.filter(id=employee_id).exists():
            return JsonResponse({'code': 401, 'msg': '请先登录！'})

        # 获取视频资源，校验类型
        try:
            resource = CourseResource.objects.get(id=resource_id, resource_type='video')
            # 校验文件是否存在
            file_path = os.path.join(settings.MEDIA_ROOT, resource.file.name)
            if not os.path.exists(file_path):
                return JsonResponse({'code': 404, 'msg': '视频文件不存在！'})

            # 返回视频文件（支持流式播放）
            response = FileResponse(open(file_path, 'rb'))
            response['Content-Type'] = 'video/mp4'
            response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
            return response
        except CourseResource.DoesNotExist:
            return JsonResponse({'code': 400, 'msg': '非视频资源或资源不存在！'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': f'服务器错误：{str(e)}'})


# 2. 学习状态更新接口（视频播放完成标记）
class UpdateLearningStatusView(View):
    def post(self, request):
        employee_id = request.POST.get('employee_id')
        chapter_id = request.POST.get('chapter_id')
        play_progress = request.POST.get('play_progress', 0)  # 播放进度（秒）

        if not employee_id or not chapter_id:
            return JsonResponse({'code': 400, 'msg': '参数缺失！'})

        try:
            employee = Employee.objects.get(id=employee_id)
            chapter = CourseChapter.objects.get(id=chapter_id)

            # 获取/创建学习记录
            record, created = LearningRecord.objects.get_or_create(
                employee=employee,
                chapter=chapter,
                defaults={'play_progress': play_progress}
            )

            # 核心：如果播放进度≥视频总时长（前端传100表示完成），标记为已完成
            if int(play_progress) >= 100:
                record.is_completed = True
                record.complete_time = timezone.now()
            else:
                record.play_progress = play_progress  # 更新播放进度

            record.save()
            return JsonResponse({'code': 200, 'msg': '状态更新成功！', 'data': {'is_completed': record.is_completed}})
        except (Employee.DoesNotExist, CourseChapter.DoesNotExist):
            return JsonResponse({'code': 404, 'msg': '员工或章节不存在！'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': f'服务器错误：{str(e)}'})


# 3. 学习路径校验接口（强制按顺序学习）
class CheckLearningPathView(View):
    def get(self, request):
        employee_id = request.GET.get('employee_id')
        chapter_id = request.GET.get('chapter_id')

        if not employee_id or not chapter_id:
            return JsonResponse({'code': 400, 'msg': '参数缺失！'})

        try:
            employee = Employee.objects.get(id=employee_id)
            current_chapter = CourseChapter.objects.get(id=chapter_id)
            course = current_chapter.course  # 关联课程

            # 获取该课程下所有章节（按sort排序）
            chapters = CourseChapter.objects.filter(course=course).order_by('sort')
            chapter_list = list(chapters)
            current_index = chapter_list.index(current_chapter)

            # 校验：如果不是第一章，检查上一章节是否完成
            if current_index > 0:
                prev_chapter = chapter_list[current_index - 1]
                prev_record = LearningRecord.objects.filter(
                    employee=employee,
                    chapter=prev_chapter,
                    is_completed=True
                ).exists()
                if not prev_record:
                    return JsonResponse({
                        'code': 403,
                        'msg': f'请先完成上一章节「{prev_chapter.name}」的学习！',
                        'data': {'prev_chapter_name': prev_chapter.name}
                    })

            # 校验通过
            return JsonResponse({'code': 200, 'msg': '可学习该章节！'})
        except (Employee.DoesNotExist, CourseChapter.DoesNotExist):
            return JsonResponse({'code': 404, 'msg': '员工或章节不存在！'})
        except ValueError:
            return JsonResponse({'code': 400, 'msg': '章节不属于该课程！'})
        except Exception as e:
            return JsonResponse({'code': 500, 'msg': f'服务器错误：{str(e)}'})