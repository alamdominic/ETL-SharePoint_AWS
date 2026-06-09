FROM public.ecr.aws/lambda/python:3.12

# Copy dependency manifest first to leverage Docker layer cache:
# pip install only re-runs when requirements.txt changes, not on every code edit.
COPY requirements.txt ${LAMBDA_TASK_ROOT}/

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# Copy application source code.
# LAMBDA_TASK_ROOT (/var/task) is on PYTHONPATH — packages at this level
# are directly importable by Lambda without any sys.path manipulation.
COPY app/ ${LAMBDA_TASK_ROOT}/app/
COPY lambda_handler.py ${LAMBDA_TASK_ROOT}/

# Lambda handler entrypoint: <module_name>.<function_name>
CMD ["lambda_handler.lambda_handler"]
