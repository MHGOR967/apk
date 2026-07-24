FROM openjdk:17-jdk-slim-buster

# Install Python and other necessary tools
RUN apt-get update && apt-get install -y python3 python3-pip wget unzip && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set python3 as default python
RUN ln -s /usr/bin/python3 /usr/bin/python

WORKDIR /app

# Install Android SDK tools
ENV ANDROID_SDK_ROOT /opt/android-sdk
ENV PATH $PATH:$ANDROID_SDK_ROOT/cmdline-tools/latest/bin:$ANDROID_SDK_ROOT/platform-tools

RUN mkdir -p $ANDROID_SDK_ROOT/cmdline-tools && \
    wget -q -O /tmp/sdk-tools.zip https://dl.google.com/android/repository/commandlinetools-linux-10406996_latest.zip && \
    unzip -q /tmp/sdk-tools.zip -d $ANDROID_SDK_ROOT/cmdline-tools && \
    mv $ANDROID_SDK_ROOT/cmdline-tools/cmdline-tools $ANDROID_SDK_ROOT/cmdline-tools/latest && \
    rm /tmp/sdk-tools.zip

# Accept licenses and install build-tools
RUN yes | sdkmanager --licenses && \
    sdkmanager "build-tools;33.0.0"

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data/apks /app/data/keystore /app/temp

# Generate Keystore
RUN keytool -genkeypair -v -keystore /app/data/keystore/debug.jks \
    -storepass android -alias androiddebugkey -keypass android \
    -keyalg RSA -keysize 2048 -validity 10000 \
    -dname "CN=Android Debug,O=Android,C=US"

ENV TELEGRAM_BOT_TOKEN="8253284488:AAFcB6N0UVY-aramsPIAhaKJNUrFsEtrQ4Q"

CMD ["python3", "src/main.py"]
