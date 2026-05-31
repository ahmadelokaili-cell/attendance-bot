
import telebot
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import pytz

BOT_TOKEN = "8712576052:AAHNWruSqr9A1xAroyC4NZiZqyYjcq03i3c"
SHEET_NAME = "Attendance"

JORDAN_TZ = pytz.timezone("Asia/Amman")

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_name(
    "credentials.json",
    scope
)

client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

bot = telebot.TeleBot(BOT_TOKEN)

# إنشاء العناوين إذا لم تكن موجودة
headers = [
    "Date",
    "Employee Name",
    "Telegram ID",
    "Check In",
    "Check Out",
    "Work Hours",
    "Overtime",
    "Delay Minutes",
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

@bot.message_handler(commands=['start'])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("حضور")
    markup.row("خروج")

    bot.send_message(
        message.chat.id,
        "أهلاً بك في نظام حضور منجرة آل شوقة",
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "حضور")
def checkin(message):

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
        "Checked In"
    ])

    bot.reply_to(
        message,
        f"✅ تم تسجيل الحضور\nالوقت: {check_in}"
    )

@bot.message_handler(func=lambda m: m.text == "خروج")
def checkout(message):

    date = today_date()
    telegram_id = str(message.from_user.id)
    checkout_time = current_time()

    records = sheet.get_all_records()

    for idx, row in enumerate(records, start=2):

        if str(row["Telegram ID"]) == telegram_id and row["Date"] == date:

            if row["Check Out"]:
                bot.reply_to(message, "تم تسجيل الخروج مسبقاً.")
                return

            checkin_dt = datetime.strptime(
                row["Check In"],
                "%H:%M:%S"
            )

            checkout_dt = datetime.strptime(
                checkout_time,
                "%H:%M:%S"
            )

            work_hours = round(
                (checkout_dt - checkin_dt).total_seconds() / 3600,
                2
            )

            overtime = max(0, round(work_hours - 8, 2))

            sheet.update_cell(idx, 5, checkout_time)
            sheet.update_cell(idx, 6, work_hours)
            sheet.update_cell(idx, 7, overtime)
            sheet.update_cell(idx, 9, "Checked Out")

            bot.reply_to(
                message,
                f"🚪 تم تسجيل الخروج\n"
                f"ساعات العمل: {work_hours}\n"
                f"الإضافي: {overtime}"
            )

            return

    bot.reply_to(message, "لم يتم العثور على حضور مسجل لهذا اليوم.")

print("Bot Started...")

bot.infinity_polling()
