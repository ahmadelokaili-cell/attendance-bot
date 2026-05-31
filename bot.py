import json
import os
from oauth2client.service_account import ServiceAccountCredentials
import os
import math
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8712576052:AAHNWruSqr9A1xAroyC4NZiZqyYjcq03i3c")
SHEET_NAME = "Attendance"

WORK_LAT = 32.278445
WORK_LON = 35.896742
ALLOWED_DISTANCE = 100  # meters

JORDAN_TZ = pytz.timezone("Asia/Amman")
pending_actions = {}

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

google_creds = json.loads(os.environ["GOOGLE_CREDENTIALS"])

creds = ServiceAccountCredentials.from_json_keyfile_dict(
    google_creds,
    scope
)
)

client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

bot = telebot.TeleBot(BOT_TOKEN)

headers = [
    "Date",
    "Employee Name",
    "Telegram ID",
    "Check In",
    "Check Out",
    "Work Hours",
    "Overtime",
    "Delay Minutes",
    "Location Distance",
    "Status"
]

if sheet.row_values(1) != headers:
    sheet.clear()
    sheet.append_row(headers)

def now():
    return datetime.now(JORDAN_TZ)

def today_date():
    return now().strftime("%Y-%m-%d")

def current_time():
    return now().strftime("%H:%M:%S")

def distance_meters(lat1, lon1, lat2, lon2):
    r = 6371000
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)

    a = (
        math.sin(dp / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c

@bot.message_handler(commands=["start"])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False
    )
    markup.row("حضور")
    markup.row("خروج")
    markup.row("الحالة")

    bot.send_message(
        message.chat.id,
        "أهلاً بك في نظام حضور منجرة آل شوقة\n\n"
        "اضغط حضور أو خروج، ثم أرسل موقعك الحالي للتأكيد.",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "حضور")
def ask_checkin_location(message):
    pending_actions[message.from_user.id] = "checkin"

    keyboard = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )

    location_button = telebot.types.KeyboardButton(
        text="📍 إرسال موقعي الحالي",
        request_location=True
    )

    keyboard.add(location_button)

    bot.send_message(
        message.chat.id,
        "📍 أرسل موقعك الحالي لتأكيد الحضور.",
        reply_markup=keyboard
    )

@bot.message_handler(func=lambda m: m.text == "خروج")
def ask_checkout_location(message):
    pending_actions[message.from_user.id] = "checkout"

    keyboard = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=True
    )

    location_button = telebot.types.KeyboardButton(
        text="📍 إرسال موقعي الحالي",
        request_location=True
    )

    keyboard.add(location_button)

    bot.send_message(
        message.chat.id,
        "📍 أرسل موقعك الحالي لتأكيد الخروج.",
        reply_markup=keyboard
    )

@bot.message_handler(content_types=["location"])
def handle_location(message):
    user_id = message.from_user.id

    if user_id not in pending_actions:
        bot.reply_to(message, "اختر أولاً حضور أو خروج.")
        return

    lat = message.location.latitude
    lon = message.location.longitude

    distance = round(
        distance_meters(lat, lon, WORK_LAT, WORK_LON),
        1
    )

    if distance > ALLOWED_DISTANCE:
        pending_actions.pop(user_id, None)
        show_main_menu(message.chat.id)

        bot.reply_to(
            message,
            f"❌ لا يمكن التسجيل من خارج موقع العمل.\n"
            f"المسافة عن الموقع: {distance} متر\n"
            f"المسموح: {ALLOWED_DISTANCE} متر"
        )
        return

    action = pending_actions.pop(user_id)

    if action == "checkin":
        register_checkin(message, distance)
    elif action == "checkout":
        register_checkout(message, distance)

    show_main_menu(message.chat.id)

def show_main_menu(chat_id):
    markup = telebot.types.ReplyKeyboardMarkup(
        resize_keyboard=True,
        one_time_keyboard=False
    )
    markup.row("حضور")
    markup.row("خروج")
    markup.row("الحالة")

    bot.send_message(
        chat_id,
        "اختر العملية:",
        reply_markup=markup
    )

def register_checkin(message, distance):
    date = today_date()
    telegram_id = str(message.from_user.id)
    employee = message.from_user.full_name
    check_in = current_time()

    records = sheet.get_all_records()

    for row in records:
        if str(row["Telegram ID"]) == telegram_id and row["Date"] == date:
            bot.reply_to(message, "تم تسجيل حضورك مسبقاً اليوم.")
            return

    official_start = datetime.strptime("08:00:00", "%H:%M:%S")
    actual = datetime.strptime(check_in, "%H:%M:%S")

    delay_minutes = 0
    if actual > official_start:
        delay_minutes = int((actual - official_start).total_seconds() / 60)

    sheet.append_row([
        date,
        employee,
        telegram_id,
        check_in,
        "",
        "",
        "",
        delay_minutes,
        distance,
        "Checked In"
    ])

    bot.reply_to(
        message,
        f"✅ تم تسجيل الحضور بنجاح\n"
        f"الوقت: {check_in}\n"
        f"التأخير: {delay_minutes} دقيقة\n"
        f"المسافة عن موقع العمل: {distance} متر"
    )

def register_checkout(message, distance):
    date = today_date()
    telegram_id = str(message.from_user.id)
    checkout_time = current_time()

    records = sheet.get_all_records()

    for idx, row in enumerate(records, start=2):
        if str(row["Telegram ID"]) == telegram_id and row["Date"] == date:

            if row["Check Out"]:
                bot.reply_to(message, "تم تسجيل الخروج مسبقاً.")
                return

            checkin_dt = datetime.strptime(row["Check In"], "%H:%M:%S")
            checkout_dt = datetime.strptime(checkout_time, "%H:%M:%S")

            work_hours = round(
                (checkout_dt - checkin_dt).total_seconds() / 3600,
                2
            )

            overtime = max(0, round(work_hours - 8, 2))

            sheet.update_cell(idx, 5, checkout_time)
            sheet.update_cell(idx, 6, work_hours)
            sheet.update_cell(idx, 7, overtime)
            sheet.update_cell(idx, 9, distance)
            sheet.update_cell(idx, 10, "Checked Out")

            bot.reply_to(
                message,
                f"🚪 تم تسجيل الخروج بنجاح\n"
                f"وقت الخروج: {checkout_time}\n"
                f"ساعات العمل: {work_hours}\n"
                f"الإضافي: {overtime}\n"
                f"المسافة عن موقع العمل: {distance} متر"
            )
            return

    bot.reply_to(message, "لم يتم العثور على حضور مسجل لهذا اليوم.")

@bot.message_handler(func=lambda m: m.text == "الحالة")
def status(message):
    date = today_date()
    telegram_id = str(message.from_user.id)

    records = sheet.get_all_records()

    for row in records:
        if str(row["Telegram ID"]) == telegram_id and row["Date"] == date:
            bot.reply_to(
                message,
                f"حالتك اليوم:\n"
                f"الحضور: {row['Check In']}\n"
                f"الخروج: {row['Check Out'] or 'لم تسجل بعد'}\n"
                f"ساعات العمل: {row['Work Hours'] or 'لم تحسب بعد'}\n"
                f"الإضافي: {row['Overtime'] or '0'}\n"
                f"الحالة: {row['Status']}"
            )
            return

    bot.reply_to(message, "لا يوجد تسجيل حضور اليوم.")

print("Bot Started...")
bot.infinity_polling()