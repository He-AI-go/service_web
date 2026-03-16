import random
from django.db.models import Count
from .file_parser import QAParser
from ..models import ExamQuestion, CourseResource, Course, QuestionTypeChoices


class AIExamGenerator:
    """AI考题生成工具：按课程文档生成题目，总分100，题目10-30个"""

    @classmethod
    def generate_questions_by_resource(cls, resource_id):
        """根据单个文档生成考题"""
        resource = CourseResource.objects.get(id=resource_id)
        course = resource.course
        if resource.file_type not in ["ppt", "pptx", "doc", "docx", "pdf", "xlsx"]:
            return {"code": 400, "msg": "仅支持文档类型生成考题"}

        # 解析文档内容
        file_path = resource.file_path.path
        parser = QAParser()
        if resource.file_type == "xlsx":
            qa_data = parser.parse_xlsx(file_path)
        elif resource.file_type in ["doc", "docx"]:
            qa_data = parser.parse_docx(file_path)
        else:  # pdf
            qa_data = parser.parse_pdf(file_path)

        # 提取关键信息
        all_content = []
        for cate, qa_list in qa_data.items():
            for qa in qa_list:
                all_content.append({"question": qa["question"], "answer": qa["answer"]})
        if len(all_content) < 5:
            return {"code": 400, "msg": "文档内容不足，至少需生成5道题"}

        # 生成题目数量（10-30个）
        question_count = min(max(len(all_content), 10), 30)
        selected_content = random.sample(all_content, question_count)

        # 分配题型占比
        type_count = {
            "single": int(question_count * 0.4),
            "multiple": int(question_count * 0.3),
            "judge": int(question_count * 0.2),
            "fill": int(question_count * 0.1)
        }
        # 补全余数
        remainder = question_count - sum(type_count.values())
        for type_key in type_count.keys():
            if remainder <= 0:
                break
            type_count[type_key] += 1
            remainder -= 1

        # 计算每题分值
        score_per_question = round(100 / question_count, 1)

        # 生成考题
        generated_count = 0
        for idx, content in enumerate(selected_content):
            if generated_count >= sum(type_count.values()):
                break

            # 单选题
            if generated_count < type_count["single"]:
                q_type = "single"
                # 修正：中文变量名改为英文
                distractors = ["错误选项A", "错误选项B", "错误选项C"]
                options = [content["answer"]] + distractors
                random.shuffle(options)
                question_content = f"{content['question']}\n选项：A.{options[0]} B.{options[1]} C.{options[2]} D.{options[3]}"
                correct_answer = [chr(65 + options.index(content["answer"]))]

            # 多选题
            elif generated_count < type_count["single"] + type_count["multiple"]:
                q_type = "multiple"
                correct_answers = [content["answer"], f"{content['answer']}补充1", f"{content['answer']}补充2"]
                correct_answers = random.sample(correct_answers, random.randint(2, 3))
                distractors = ["错误选项1", "错误选项2", "错误选项3"]
                options = correct_answers + distractors
                random.shuffle(options)
                question_content = f"{content['question']}\n选项：A.{options[0]} B.{options[1]} C.{options[2]} D.{options[3]}"
                correct_answer = [chr(65 + options.index(ca)) for ca in correct_answers]

            # 判断题
            elif generated_count < type_count["single"] + type_count["multiple"] + type_count["judge"]:
                q_type = "judge"
                question_content = f"{content['question']}（对/错）"
                correct_answer = "True" if random.random() > 0.5 else "False"

            # 填空题
            else:
                q_type = "fill"
                question_content = content["question"]
                correct_answer = content["answer"].split(",")

            # 保存考题
            ExamQuestion.objects.create(
                course=course,
                resource=resource,
                question_type=q_type,
                content=question_content,
                correct_answer=",".join(correct_answer) if isinstance(correct_answer, list) else correct_answer,
                score=score_per_question
            )
            generated_count += 1

        # 调整分值确保总分100
        cls.adjust_question_scores(course.id)

        return {"code": 200, "msg": f"成功生成{generated_count}道题，总分100分"}

    @classmethod
    def adjust_question_scores(cls, course_id):
        """调整课程所有考题分值，确保总分100"""
        course = Course.objects.get(id=course_id)
        questions = ExamQuestion.objects.filter(course=course)
        question_count = questions.count()
        if question_count == 0:
            return

        score_per_question = 100 / question_count
        questions.update(score=score_per_question)

        # 修正最后一题分值
        total_score = round(score_per_question * (question_count - 1), 1)
        last_question = questions.last()
        last_question.score = round(100 - total_score, 1)
        last_question.save()

    @classmethod
    def generate_questions_on_resource_upload(cls, sender, instance, created, **kwargs):
        """信号：文档上传后自动生成考题"""
        if created and instance.file_type in ["ppt", "pptx", "doc", "docx", "pdf", "xlsx"]:
            cls.generate_questions_by_resource(instance.id)