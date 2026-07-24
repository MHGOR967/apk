
import logging
import os
import shutil
import zipfile
import asyncio
from telegram import Update, ForceReply
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot token (will be read from environment variable)
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Base APK path
BASE_APK_PATH = "/app/data/apks/base.apk"
# Keystore path
KEYSTORE_PATH = "/app/data/keystore/debug.jks"
# Keystore password (for simplicity, hardcoded for now, but should be secure)
KEYSTORE_PASSWORD = "android"
# Keystore alias
KEYSTORE_ALIAS = "androiddebugkey"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Sends a message on /start command."""
    user = update.effective_user
    await update.message.reply_html(
        f"مرحباً {user.mention_html()}!\nأنا بوت تخصيص APK. أرسل لي توكن بوت تيليجرام الخاص بك لإنشاء تطبيقك المخصص.",
        reply_markup=ForceReply(selective=True),
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles incoming messages, expecting a bot token."""
    user_id = update.effective_user.id
    user_token = update.message.text

    if not user_token or not user_token.startswith("bot"):
        await update.message.reply_text("الرجاء إرسال توكن بوت تيليجرام صالح (يجب أن يبدأ بـ 'bot').")
        return

    await update.message.reply_text("تم استلام التوكن الخاص بك. جاري تخصيص وتوقيع ملف APK...")

    # Create a unique temporary directory for the user
    user_temp_dir = os.path.join("/app/temp", str(user_id))
    os.makedirs(user_temp_dir, exist_ok=True)

    try:
        # Copy base APK to user's temp directory
        user_apk_path = os.path.join(user_temp_dir, f"custom_{user_id}.apk")
        shutil.copy(BASE_APK_PATH, user_apk_path)

        # Modify APK (write token to assets/token.txt)
        await modify_apk(user_apk_path, user_token)

        # Sign the modified APK
        signed_apk_path = await sign_apk(user_apk_path, user_temp_dir)

        # Send the signed APK back to the user
        await update.message.reply_document(document=open(signed_apk_path, 'rb'))
        await update.message.reply_text("تم إنشاء تطبيقك المخصص بنجاح!")

    except Exception as e:
        logger.error(f"Error processing APK for user {user_id}: {e}")
        await update.message.reply_text("حدث خطأ أثناء معالجة طلبك. الرجاء المحاولة مرة أخرى لاحقاً.")
    finally:
        # Clean up temporary directory
        if os.path.exists(user_temp_dir):
            shutil.rmtree(user_temp_dir)
            logger.info(f"Cleaned up temporary directory for user {user_id}")

async def modify_apk(apk_path: str, token: str) -> None:
    """Modifies the APK by writing the token to assets/token.txt."""
    # Create a temporary directory to extract APK contents
    extract_dir = apk_path + "_extracted"
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(apk_path, 'r') as apk_zip:
            apk_zip.extractall(extract_dir)

        # Write token to assets/token.txt
        assets_dir = os.path.join(extract_dir, "assets")
        os.makedirs(assets_dir, exist_ok=True)
        token_file_path = os.path.join(assets_dir, "token.txt")
        with open(token_file_path, 'w') as f:
            f.write(token)

        # Re-zip the APK
        new_apk_path = apk_path + ".modified"
        shutil.make_archive(new_apk_path.replace(".apk", ""), 'zip', extract_dir)
        os.rename(new_apk_path.replace(".zip", ".apk"), apk_path)

    finally:
        if os.path.exists(extract_dir):
            shutil.rmtree(extract_dir)

async def sign_apk(apk_path: str, output_dir: str) -> str:
    """Signs the APK using apksigner and zipalign."""
    unsigned_apk = apk_path
    aligned_apk = os.path.join(output_dir, os.path.basename(apk_path).replace(".apk", "_aligned.apk"))
    signed_apk = os.path.join(output_dir, os.path.basename(apk_path).replace(".apk", "_signed.apk"))

    # Path to Android build tools (where zipalign and apksigner are located)
    build_tools_path = "/opt/android-sdk/build-tools/33.0.0"
    zipalign_bin = os.path.join(build_tools_path, "zipalign")
    apksigner_bin = os.path.join(build_tools_path, "apksigner")

    # 1. Align the APK (important for performance)
    zipalign_command = f"{zipalign_bin} -p 4 {unsigned_apk} {aligned_apk}"
    process = await asyncio.create_subprocess_shell(
        zipalign_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"Zipalign failed: {stderr.decode()}")
    logger.info(f"Zipalign output: {stdout.decode()}")

    # 2. Sign the aligned APK using apksigner
    # apksigner sign --ks <keystore_path> --ks-pass pass:<password> --out <signed_apk> <aligned_apk>
    apksigner_command = (
        f"{apksigner_bin} sign --ks {KEYSTORE_PATH} --ks-pass pass:{KEYSTORE_PASSWORD} "
        f"--out {signed_apk} {aligned_apk}"
    )
    process = await asyncio.create_subprocess_shell(
        apksigner_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await process.communicate()
    if process.returncode != 0:
        raise Exception(f"Apksigner failed: {stderr.decode()}")
    logger.info(f"Apksigner output: {stdout.decode()}")

    return signed_apk

async def main() -> None:
    """Starts the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set.")
        return

    # Create the Application and pass it your bot's token.
    application = Application.builder().token(BOT_TOKEN).build()

    # On different commands - answer in Telegram
    application.add_handler(CommandHandler("start", start))

    # On non command messages - echo the message on Telegram
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Run the bot until the user presses Ctrl-C
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    asyncio.run(main())
