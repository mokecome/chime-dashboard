### Dockerfile
# Use an official Python runtime as a parent image
FROM python:3.12.3

# 更新 pip，這可以避免因為老版本 pip 造成的依賴解析問題
RUN pip install --upgrade pip

# 將當前目錄下的文件複製到容器的 /app 中
COPY . /app

# Set the working directory to /app
WORKDIR /app

# Copy the requirements.txt file to your image
COPY requirements.txt .

# set python dependency
RUN pip install -r requirements.txt

# Run app.py when the container launches
CMD ["python", "faq.py"]