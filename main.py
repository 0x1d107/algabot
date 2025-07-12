from telegram import Update
from datetime import datetime,timedelta,UTC
import httpx
from telegram.ext import ApplicationBuilder,ContextTypes,CommandHandler,JobQueue
from botconfig import BOT_TOKEN,BOT_DATABASE,DEFAULT_THRESHOLD
import sqlite3
import urllib.parse

def luhn_check(card_number):
    digit_sum = 0
    parity = len(card_number)%2
    for i,c in enumerate(card_number):
        digit = int(c)
        if i % 2 == parity:
            digit*=2
            if digit > 9:
                digit -= 9
        digit_sum+=digit
    return digit_sum %10 == 0

help_text="""
Привет. Это бот для рассылки напоминаний о низком балансе карты АЛГА.
Для того чтобы привязать карту, используй команду /setcard `<номер_карты>`.
Чтобы отвязать карту и перестать получать уведомления воспользуйся командой /reset.
"""
low_balance_text = """
Баланс карты ({} руб.) ниже заданного порогового значения. Рекомендуется пополнить баланс.
"""

async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,text=help_text,parse_mode="Markdown")
async def setcard(update:Update,context:ContextTypes.DEFAULT_TYPE):
    command_help = "Пожалуйста, напишите номер карты сразу после команды, например так: `/setcard 123456789012345679`"
    if len(context.args) == 0:
        await context.bot.send_message(chat_id=update.effective_chat.id,text="Не указан номер карты. "+command_help,parse_mode="Markdown")
        return 
    card_number = ''.join(context.args)
    if not card_number.isdigit():
        await context.bot.send_message(chat_id=update.effective_chat.id,text="Указанный номер содержит нецифровые символы. "+command_help,parse_mode="Markdown")
        return
    if not luhn_check(card_number):
        await context.bot.send_message(chat_id=update.effective_chat.id,text="Указанный номер не является корректным, проверьте написание номера.",parse_mode="Markdown")
        return
    balance = await get_balance(card_number)
    if balance is None:
        await context.bot.send_message(chat_id=update.effective_chat.id,text="Не удалось получить баланс карты. К сожалению, такую карту привязать нельзя.",parse_mode="Markdown")
        return 
    conn = sqlite3.connect(BOT_DATABASE)
    conn.execute("REPLACE INTO algabot VALUES (?,?,?)",(update.effective_chat.id,card_number,100))
    conn.commit()
    conn.close()
    await context.bot.send_message(chat_id=update.effective_chat.id,text=f"Карта успешно привязана. Баланс карты: {balance} руб.")
async def resetcard(update:Update,context:ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(BOT_DATABASE)
    conn.execute("DELETE FROM algabot where chat_id = ?",(update.effective_chat.id,))
    conn.commit()
    conn.close()
    await context.bot.send_message(chat_id=update.effective_chat.id,text="Удалена привязка карты")

async def get_balance(card_number:str) -> float :
    async with httpx.AsyncClient() as client:
        result = await client.post("https://pay.brsc.ru/Alga.pay/GoldenCrownSite.php",data={'cardnumber':card_number})
        if not result.is_redirect:
            print('response was not redirect!')
            conn.close()
            return None
        urlquery = urllib.parse.urlparse(result.headers['location']).query
        qs = urllib.parse.parse_qs(urlquery)
        if 'sum' in qs:
            balance = qs['sum'][0]
            return float(balance)
        print("No sum in query string:",qs)
        return None
    
async def remind_callback(ctx:ContextTypes.DEFAULT_TYPE):
    print("remind")
    conn = sqlite3.connect(BOT_DATABASE)
    for row in conn.execute("SELECT * FROM algabot") :
        card_number = row[1]
        balance = await get_balance(card_number)
        if balance is None:
            print("Can't get balance of card",card_number)
            continue
        if balance < row[2]:
            await ctx.bot.send_message(row[0],text=low_balance_text.format(balance))
        else:
            await ctx.bot.send_message(row[0],text=f"OK balance of {balance}")

    conn.close()

        
if __name__ == "__main__":
    queue = JobQueue()
    application = ApplicationBuilder().token(BOT_TOKEN).job_queue(queue).build()
    queue.run_daily(remind_callback,datetime.now(UTC)+timedelta(seconds=5))
    start_handler = CommandHandler('start',start)
    application.add_handler(start_handler)
    application.add_handler(CommandHandler('setcard',setcard))
    application.add_handler(CommandHandler('reset',resetcard))
    application.run_polling()
