FROM amazoncorretto:17-alpine

# تثبيت Python والأدوات اللازمة لبناء المكتبات
RUN apk add --no-cache python3 py3-pip wget unzip bash build-base python3-dev libffi-dev

# إعداد بيئة العمل
WORKDIR /app

# إعداد أدوات الأندرويد (SDK)
ENV ANDROID_SDK_ROOT /opt/android-sdk
ENV PATH $PATH:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools

RUN mkdir -p $ANDROID_SDK_ROOT/cmdline-tools && \
    wget -q -O /tmp/sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-10406996_latest.zip && \
    unzip -q /tmp/sdk-tools.zip -d $ANDROID_SDK_ROOT/cmdline-tools && \
    mv $ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools $ANDROID_SDK_ROOT/cmdline-tools/latest && \
    rm /tmp/sdk-tools.zip

# قبول التراخيص وتثبيت أدوات البناء
RUN yes | sdkmanager --licenses && \
    sdkmanager "build-tools;33.0.0"

# إنشاء بيئة افتراضية لـ Python لتجنب مشاكل الصلاحيات
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# تثبيت مكتبات Python
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# نسخ باقي ملفات المشروع
COPY . .

# إنشاء المجلدات اللازمة
RUN mkdir -p /app/data/apks /app/data/keystore /app/temp

# توليد مفتاح التوقيع
RUN keytool -genkeypair -v -keystore /app/data/keystore/debug.jks \
    -storepass android -alias androiddebugkey -keypass android \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US"

# توكن البوت
ENV TELEGRAM_BOT_TOKEN="8253284488:AAFcB6N0UVY-aramsPIAhaKJNUrFsEtrQ4Q"

# تشغيل البوت
CMD ["python3", "src/main.py"]
