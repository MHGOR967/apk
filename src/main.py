import logging
import os
import shutil
import zipfile
import asyncio
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# إعداد السجلات (Logging)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# توكن البوت
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# المسارات الأساسية
BASE_APK_PATH = "/app/data/apks/base.apk"
KEYSTORE_PATH = "/app/data/keystore/debug.jks"
KEYSTORE_PASSWORD = "android"
KEYSTORE_ALIAS = "androiddebugkey"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يستجيب لأمر /start"""
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}!\nأنا بوت تخصيص APK. أرسل لي توكن بوت تيليجرام الخاص بك لإنشاء تطبيقك المخصص.",
        reply_markup=ForceReply(selective=True),
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """يعالج الرسائل الواردة (يتوقع توكن البوت)"""
    user_id = update.effective_user.id
    user_token = update.message.text

    if not user_token or ":" not in user_token:
        await update.message.reply_text("الرجاء إرسال توكن بوت تيليجرام صالح.")
        return

    status_message = await update.message.reply_text("تم استلام التوكن. جاري معالجة الـ APK...")

    # إنشاء مجلد مؤقت فريد للمستخدم لضمان العزل التام
    user_temp_dir = os.path.join("/app/temp", str(user_id))
    os.makedirs(user_temp_dir, exist_ok=True)

    try:
        user_apk_path = os.path.join(user_temp_dir, f"custom_{user_id}.apk")
        
        # التأكد من وجود ملف القالب
        if not os.path.exists(BASE_APK_PATH):
            await update.message.reply_text("خطأ: ملف base.apk غير موجود في السيرفر.")
            return

        # نسخ القالب للمجلد المؤقت
        shutil.copy(BASE_APK_PATH, user_apk_path)

        # تعديل الـ APK (إضافة التوكن)
        await status_message.edit_text("جاري تعديل محتويات الـ APK...")
        await modify_apk(user_apk_path, user_token)

        # توقيع الـ APK
        await status_message.edit_text("جاري توقيع التطبيق...")
        signed_apk_path = await sign_apk(user_apk_path, user_temp_dir)

        # إرسال الملف للمستخدم
        await status_message.edit_text("تم بنجاح! جاري رفع الملف...")
        with open(signed_apk_path, 'rb') as apk_file:
            await update.message.reply_document(
                document=apk_file,
                filename="custom_app.apk",
                caption="تطبيقك المخصص جاهز!"
            )

    except Exception as e:
        logger.error(f"Error for user {user_id}: {e}")
        await update.message.reply_text(f"حدث خطأ أثناء المعالجة: {str(e)}")
    finally:
        # التنظيف الفوري للمجلد المؤقت
        if os.path.exists(user_temp_dir):
            shutil.rmtree(user_temp_dir)
            logger.info(f"Cleaned up for user {user_id}")

async def modify_apk(apk_path: str, token: str) -> None:
    """تعديل ملف assets/token.txt داخل الـ APK"""
    temp_extract = apk_path + "_temp"
    os.makedirs(temp_extract, exist_ok=True)
    
    try:
        with zipfile.ZipFile(apk_path, 'r') as zip_ref:
            zip_ref.extractall(temp_extract)
        
        assets_path = os.path.join(temp_extract, "assets")
        os.makedirs(assets_path, exist_ok=True)
        
        with open(os.path.join(assets_path, "token.txt"), "w") as f:
            f.write(token)
            
        shutil.make_archive(apk_path.replace(".apk", ""), 'zip', temp_extract)
        os.rename(apk_path.replace(".apk", ".zip"), apk_path)
    finally:
        shutil.rmtree(temp_extract)

async def sign_apk(apk_path: str, output_dir: str) -> str:
    """توقيع الـ APK باستخدام أدوات الأندرويد"""
    aligned_apk = os.path.join(output_dir, "aligned.apk")
    signed_apk = os.path.join(output_dir, "signed.apk")
    
    build_tools = "/opt/android-sdk/build-tools/33.0.0"
    zipalign = os.path.join(build_tools, "zipalign")
    apksigner = os.path.join(build_tools, "apksigner")

    # 1. Zipalign
    cmd_align = f"{zipalign} -p 4 {apk_path} {aligned_apk}"
    proc = await asyncio.create_subprocess_shell(cmd_align, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

    # 2. Apksigner
    cmd_sign = f"{apksigner} sign --ks {KEYSTORE_PATH} --ks-pass pass:{KEYSTORE_PASSWORD} --out {signed_apk} {aligned_apk}"
    proc = await asyncio.create_subprocess_shell(cmd_sign, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()

    return signed_apk

def main() -> None:
    """تشغيل البوت"""
    if not BOT_TOKEN:
        logger.error("No BOT_TOKEN found!")
        return

    # بناء التطبيق بالطريقة الصحيحة للإصدار الحديث
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # بدء البوت
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
