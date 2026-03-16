from django.http import JsonResponse
from django.shortcuts import redirect, reverse
from functools import wraps
from django.contrib.auth import get_user_model
from .models import Employee, StatusChoices

# 获取Django超级管理员模型
User = get_user_model()


def employee_login_required(func):
    """员工登录验证装饰器：仅启用状态员工可访问"""

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        employee_id = request.session.get('employee_id')
        if not employee_id:
            return redirect(reverse('training:login'))
        try:
            employee = Employee.objects.get(employee_id=employee_id, status=StatusChoices.ENABLE)
        except Employee.DoesNotExist:
            request.session.flush()
            return JsonResponse({'code': 403, 'msg': '账号已禁用或不存在，请重新登录'}, status=403)
        request.employee = employee
        return func(request, *args, **kwargs)

    return wrapper


def admin_login_required(func):
    """管理员登录验证装饰器：仅Django超级管理员可访问平台整体数据"""

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        # 管理员从Django admin会话获取
        admin_id = request.session.get('admin_id')
        if not admin_id:
            return redirect(reverse('admin:login'))  # 跳转到Django后台登录
        try:
            admin = User.objects.get(id=admin_id, is_superuser=True, is_active=True)
        except User.DoesNotExist:
            request.session.flush()
            return JsonResponse({'code': 403, 'msg': '非管理员账号，无访问权限'}, status=403)
        request.admin = admin
        return func(request, *args, **kwargs)

    return wrapper


def course_stat_view_required(func):
    """课程统计视图装饰器：员工/管理员均可访问，自动区分数据范围"""

    @wraps(func)
    def wrapper(request, *args, **kwargs):
        # 先判断是否为管理员
        admin_id = request.session.get('admin_id')
        if admin_id:
            try:
                admin = User.objects.get(id=admin_id, is_superuser=True, is_active=True)
                request.is_admin = True
                request.admin = admin
                return func(request, *args, **kwargs)
            except User.DoesNotExist:
                pass  # 不是管理员，继续判断员工

        # 再判断是否为员工
        employee_id = request.session.get('employee_id')
        if not employee_id:
            return redirect(reverse('training:login'))
        try:
            employee = Employee.objects.get(employee_id=employee_id, status=StatusChoices.ENABLE)
            request.is_admin = False
            request.employee = employee
            return func(request, *args, **kwargs)
        except Employee.DoesNotExist:
            request.session.flush()
            return JsonResponse({'code': 403, 'msg': '账号无访问权限'}, status=403)

    return wrapper  # 关键：确保装饰器返回wrapper函数